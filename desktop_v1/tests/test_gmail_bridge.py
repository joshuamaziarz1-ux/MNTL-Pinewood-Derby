import json

from gmail_bridge import _division, filter_new_signups, parse_bridge_payload


def test_parse_bridge_payload_accepts_json_and_jsonp():
    obj = {"ok": True, "registrations": [{"messageId": "abc", "name": "Racer"}]}
    assert parse_bridge_payload(json.dumps(obj)) == obj
    assert parse_bridge_payload("mnltDesktopCallback(" + json.dumps(obj) + ");") == obj


def test_division_mapping_handles_snappages_labels():
    assert _division("Traditional") == "Traditional"
    assert _division("Fully Modified Race") == "Modified"
    assert _division("Both Races") == "Both"


def test_filter_new_signups_deduplicates_by_message_and_racer_name():
    state = {
        "registrations": [
            {"name": "Existing Racer", "sourceMessageId": "already-imported"},
        ]
    }
    rows = [
        {"messageId": "already-imported", "name": "Different Name"},
        {"messageId": "new-1", "name": "Existing Racer"},
        {"messageId": "ignored-1", "name": "Ignored Racer"},
        {"messageId": "new-2", "name": "New Racer", "receivedAt": "2026-08-27T08:00:00"},
    ]
    out = filter_new_signups(state, rows, ["ignored-1"])
    assert [x["messageId"] for x in out] == ["new-2"]


def test_requests_client_is_available():
    import gmail_bridge
    assert hasattr(gmail_bridge, "requests")


def test_parse_bridge_payload_accepts_wrapper_variants():
    import json
    from gmail_bridge import parse_bridge_payload

    obj = {"ok": True, "registrations": [{"messageId": "m1", "name": "Racer"}]}
    raw = json.dumps(obj)
    assert parse_bridge_payload("/**/__mnltBridge_desktop(" + raw + ");") == obj
    assert parse_bridge_payload("__mnltBridge_desktop && __mnltBridge_desktop(" + raw + ");") == obj
    assert parse_bridge_payload(")]}'\n" + raw) == obj


def test_load_bridge_connection_file(tmp_path):
    import json
    from gmail_bridge import load_bridge_connection_file

    path = tmp_path / "MNLT_Derby_Connection.mnltbridge"
    path.write_text(json.dumps({
        "type": "mnlt-derby-bridge",
        "version": 1,
        "url": "https://script.google.com/macros/s/TEST/exec",
        "key": "secret-key"
    }), encoding="utf-8")

    cfg = load_bridge_connection_file(path)
    assert cfg["url"].endswith("/exec")
    assert cfg["key"] == "secret-key"
