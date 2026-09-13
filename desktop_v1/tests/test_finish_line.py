import copy
import os
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtWidgets import QApplication, QWidget
from finish_line import FinishLineWindow, current_payload, heat_payload
from race_engine import build_fair_schedule
from storage import fresh_state


@pytest.fixture(scope='module')
def qt():
    return QApplication.instance() or QApplication([])


def manager():
    state = fresh_state()
    state['registrations'] = [
        {'id': i, 'name': f'Full Name {i}', 'tradCar': f'Car {i}', 'contact': 'PRIVATE'}
        for i in range(1, 5)]
    state['racers'] = [{'id': i, 'registrationId': i, 'name': 'Stale name'} for i in range(1, 5)]
    state['heats'] = build_fair_schedule([1, 2, 3, 4])
    m = SimpleNamespace(state=state, current_division='Traditional', store=SimpleNamespace(find_photo=lambda rid, div: None))
    m.traditional = SimpleNamespace(
        division='Traditional', _control_heats=lambda: (state['heats'], state['current']),
        _runoff=lambda: None)
    return m


def test_public_payload_current_names_lanes_and_no_mutation():
    m = manager()
    before = copy.deepcopy(m.state)
    payload = current_payload(m, 'Traditional')
    assert payload['mode'] == 'lineup'
    for e, rid in zip(payload['entries'], m.state['heats'][0]['lanes']):
        assert e['id'] == str(rid)
        assert e['name'] == f'Full Name {rid}'
        assert e['car'] == f'Car {rid}'
    assert 'PRIVATE' not in str(payload)
    assert m.state == before


def test_countdown_duplicate_cancel_and_heat_change(qt):
    m = QWidget()
    m.__dict__.update(manager().__dict__)
    w = FinishLineWindow(m)
    before = copy.deepcopy(m.state)
    w.start_countdown()
    w.tick()
    assert w.count == 2
    w.start_countdown()
    assert w.count == 2
    w.sync()
    assert w.mode == 'countdown'
    w.sync(force=True)
    assert not w.count_timer.isActive()
    assert w.mode == 'lineup'
    assert m.state == before
    w.start_countdown()
    m.state['current'] = 1
    w.sync()
    assert w.mode == 'lineup'
    assert not w.count_timer.isActive()
    w.close()
    w.audio.shutdown()


def test_saved_result_hold_and_sparse_lanes(qt):
    m = QWidget()
    m.__dict__.update(manager().__dict__)
    w = FinishLineWindow(m)
    heat = {'id': 1, 'lanes': [1, None, 3, None], 'results': [
        {'racer_id': 3, 'position': 1}, {'racer_id': 1, 'position': 2}]}
    w.saved('Traditional', heat, 4, None)
    w.sync()
    assert w.mode == 'results'
    assert w.result_timer.isActive()
    assert [(e['lane'], e['place']) for e in w.payload['entries']] == [(1, 2), (3, 1)]
    w.return_live()
    assert w.mode == 'lineup'
    w.close()
    w.audio.shutdown()


def test_modified_and_runoff_use_correct_bucket():
    m = manager()
    m.state['modified']['raceRacers'] = m.state['racers']
    m.state['modified']['runoff'] = {'attempt': 2, 'current': 0, 'currentIds': [2, 4],
        'heats': [{'id': 1, 'lanes': [None, 2, None, 4], 'results': []}]}
    p = current_payload(m, 'Modified')
    assert p['runoff'] == 2
    assert [e['lane'] for e in p['entries']] == [2, 4]
    m.state['modified']['runoff']['completed'] = True
    assert current_payload(m, 'Modified')['mode'] == 'tie'


def test_complete_tied_field_never_invents_trophy_winner():
    m = manager()
    for heat in m.state['heats']:
        heat['results'] = [{'racer_id': rid, 'position': lane+1, 'points': lane+1}
                           for lane, rid in enumerate(heat['lanes'])]
    assert current_payload(m, 'Traditional')['mode'] == 'tie'
