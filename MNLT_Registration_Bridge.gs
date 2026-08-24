/**
 * MNLT Derby Registration Bridge
 *
 * Free Google Apps Script bridge for the MNLT Derby Manager.
 * Run this script while signed into the Gmail account that receives the
 * SnapPages derby registration emails.
 */

const MNLT_QUERY = 'from:no-reply@snappages.com subject:"Sukkot 2026 Pinewood Derby Sign Up - Submission" -in:trash -in:spam';
const MAX_THREADS = 60;

function setupBridge() {
  const props = PropertiesService.getScriptProperties();
  let key = props.getProperty('MNLT_BRIDGE_KEY');
  if (!key) {
    key = Utilities.getUuid().replace(/-/g, '') + Utilities.getUuid().replace(/-/g, '');
    props.setProperty('MNLT_BRIDGE_KEY', key);
  }
  console.log('MNLT BRIDGE KEY: ' + key);
  return key;
}

function doGet(e) {
  const callback = safeCallback_(e && e.parameter ? e.parameter.callback : '');
  const suppliedKey = String(e && e.parameter ? (e.parameter.key || '') : '');
  const expectedKey = PropertiesService.getScriptProperties().getProperty('MNLT_BRIDGE_KEY');

  let payload;
  if (!expectedKey) {
    payload = { ok: false, error: 'Bridge is not initialized. Run setupBridge() once.' };
  } else if (!constantTimeEqual_(suppliedKey, expectedKey)) {
    payload = { ok: false, error: 'Unauthorized' };
  } else {
    try {
      payload = {
        ok: true,
        checkedAt: new Date().toISOString(),
        registrations: getRegistrations_()
      };
    } catch (err) {
      payload = { ok: false, error: String(err && err.message ? err.message : err) };
    }
  }

  const json = JSON.stringify(payload);
  if (callback) {
    return ContentService.createTextOutput(callback + '(' + json + ');')
      .setMimeType(ContentService.MimeType.JAVASCRIPT);
  }
  return ContentService.createTextOutput(json)
    .setMimeType(ContentService.MimeType.JSON);
}

function getRegistrations_() {
  const threads = GmailApp.search(MNLT_QUERY, 0, MAX_THREADS);
  const out = [];

  threads.forEach(thread => {
    thread.getMessages().forEach(message => {
      if (message.isInTrash()) return;
      const subject = String(message.getSubject() || '');
      if (subject.indexOf('Sukkot 2026 Pinewood Derby Sign Up - Submission') === -1) return;

      const body = String(message.getPlainBody() || '');
      const firstName = field_(body, 'First Name');
      const lastName = field_(body, 'Last Name');
      const email = field_(body, 'Email');
      const phone = field_(body, 'Phone Number');
      const choice = field_(body, 'Multiple Choice');
      const name = (firstName + ' ' + lastName).trim();
      if (!name) return;

      out.push({
        messageId: String(message.getId()),
        receivedAt: message.getDate().toISOString(),
        name: name,
        firstName: firstName,
        lastName: lastName,
        email: email,
        phone: phone,
        choice: choice,
        division: mapDivision_(choice)
      });
    });
  });

  out.sort((a, b) => new Date(b.receivedAt).getTime() - new Date(a.receivedAt).getTime());
  return out.slice(0, 100);
}

function field_(text, label) {
  const lines = String(text || '')
    .replace(/\r/g, '')
    .split('\n')
    .map(s => s.trim())
    .filter(Boolean);
  const target = String(label || '').toLowerCase();

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const lower = line.toLowerCase();
    if (lower === target) return cleanValue_(lines[i + 1] || '');
    if (lower.indexOf(target + ':') === 0) return cleanValue_(line.slice(label.length + 1));
    if (lower.indexOf(target + ' -') === 0) return cleanValue_(line.slice(label.length + 2));
  }
  return '';
}

function cleanValue_(value) {
  return String(value || '')
    .replace(/^[:\-\s]+/, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function mapDivision_(choice) {
  const c = String(choice || '').toLowerCase();
  if (c.indexOf('both') !== -1) return 'Both';
  if (c.indexOf('modified') !== -1) return 'Modified';
  if (c.indexOf('traditional') !== -1) return 'Traditional';
  return '';
}

function safeCallback_(name) {
  name = String(name || '');
  return /^[A-Za-z_$][0-9A-Za-z_$\.]*$/.test(name) ? name : '';
}

function constantTimeEqual_(a, b) {
  a = String(a || '');
  b = String(b || '');
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}
