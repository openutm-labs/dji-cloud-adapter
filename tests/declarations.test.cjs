const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('src/dji_cloud_adaptor/web/declarations.js', 'utf8');

function page({lostPrepare = false, loseAction = '', language = 'en'} = {}) {
  const nodes = new Map(), calls = [], records = [];
  let outage = false, revision = 0;
  const node = id => {
    if (!nodes.has(id)) nodes.set(id, {hidden: false, disabled: false, value: '', textContent: '', listeners: {},
      appendChild(child) { if (!this.value) this.value = child.value; },
      addEventListener(event, fn) { this.listeners[event] = fn; }});
    return nodes.get(id);
  };
  const context = {window: {}, document: {getElementById: node, querySelectorAll: () => [], createElement: () => ({})}};
  vm.createContext(context);
  vm.runInContext(source, context);
  const api = async (url, body) => {
    calls.push({url, body: body && JSON.parse(JSON.stringify(body))});
    if (outage) throw new Error('offline');
    if (url === '/api/pilot/declarations' && !body) return {
      enabled: true, request_id: 'request-' + revision++, server_time: Date.now()/1000,
      pilots: [{id: 'pilot1', name: 'Pilot'}], aircraft: [{serial: 'AIRCRAFT', name: 'Aircraft'}],
      limits: {radius_m: 500, height_m: 100, duration_minutes: 60}, operations: structuredClone(records),
    };
    if (url === '/api/pilot/declarations') {
      const existing = records.find(op => op.id === body.request_id);
      if (existing) return structuredClone(existing);
      const op = {id: body.request_id, aircraft_sn: body.aircraft_sn, pilot_name: 'Pilot',
        stage: 'prepared', state: 'unknown', approved: false, plan: body, checked_at: null,
        start: body.start, end: new Date(Date.parse(body.start)+body.duration_minutes*60000).toISOString(),
        geometry: {features: [{properties: {takeoff_reference: {lat: 1, lon: 2}, min_altitude: {meters: 10}, max_altitude: {meters: 60}}}]},
        telemetry_counts: {}};
      records.unshift(op);
      if (lostPrepare) {lostPrepare = false; throw new Error('offline');}
      return structuredClone(op);
    }
    const op = records.find(row => row.id === url.split('/').at(-1));
    if (body.action === 'submit') Object.assign(op, {stage: 'submitted', state: 'accepted', approved: true, declaration_id: 'remote-id', checked_at: Date.now()/1000});
    if (body.action === 'activate') op.state = 'activated';
    if (body.action === 'finish') Object.assign(op, {stage: 'closed', state: 'ended'});
    if (body.action === 'discard') op.stage = 'discarded';
    if (body.action === loseAction) {loseAction = ''; throw new Error('offline');}
    return structuredClone(op);
  };
  const view = context.window.PilotDeclarations({api, language: () => language, aircraftSerial: () => 'AIRCRAFT'});
  const click = action => node('declaration-' + action).listeners.click();
  return {node, calls, records, view, click,
    outage(value) {outage = value;},
    async prepare() {
      node('declaration-radius').value = '100'; node('declaration-height').value = '50';
      node('declaration-duration').value = '30'; node('declaration-start').value = '2030-01-01T12:00';
      node('declaration-ground').checked = true;
      await node('declaration-form').listeners.submit({preventDefault() {}});
    },
  };
}

test('disabled deployments make no declaration requests', async () => {
  const p = page();
  await p.view.connect({declarations_enabled: false});
  await p.view.poll();
  assert.equal(p.calls.length, 0);
  assert.equal(p.node('declaration-card').hidden, true);
});

test('review is separate from submit and activation; no flight control request', async () => {
  const p = page();
  await p.view.connect({declarations_enabled: true});
  await p.prepare();
  assert.equal(p.node('declaration-form').hidden, true);
  assert.equal(p.node('declaration-submit').hidden, false);
  assert.equal(p.node('declaration-activate').hidden, true);
  assert.match(p.node('declaration-summary').textContent, /1.000000, 2.000000/);
  assert(!p.calls.some(call => call.body && call.body.action));
  await p.click('submit');
  assert.equal(p.node('declaration-submit').hidden, true);
  assert.equal(p.node('declaration-activate').hidden, false);
  await p.click('activate');
  assert.equal(p.node('declaration-finish').hidden, false);
  await p.click('finish');
  assert.equal(p.node('declaration-form').hidden, false);
  assert(p.calls.every(call => call.url.startsWith('/api/pilot/declarations')));
});

test('lost prepare response recovers the same plan without a new request ID', async () => {
  const p = page({lostPrepare: true});
  await p.view.connect({declarations_enabled: true});
  await p.prepare();
  assert.equal(p.node('declaration-prepare').disabled, true);
  await p.click('refresh');
  const prepares = p.calls.filter(call => call.body && call.body.request_id);
  assert.equal(prepares.length, 2);
  assert.deepEqual(prepares[0].body, prepares[1].body);
  assert.equal(p.records.length, 1);
  assert.equal(p.node('declaration-submit').hidden, false);
});

test('reopening restores a submitted declaration and never submits it again', async () => {
  const p = page({loseAction: 'submit'});
  await p.view.connect({declarations_enabled: true});
  await p.prepare();
  await p.click('submit');
  p.view.clear();
  await p.view.connect({declarations_enabled: true});
  assert.equal(p.node('declaration-submit').hidden, true);
  assert.match(p.node('declaration-status').textContent, /Accepted/);
  assert.equal(p.calls.filter(call => call.body && call.body.action === 'submit').length, 1);
});

test('unconfirmed and stale states do not expose activation', async () => {
  const p = page();
  await p.view.connect({declarations_enabled: true});
  await p.prepare();
  Object.assign(p.records[0], {stage: 'uncertain', state: 'unknown'});
  await p.view.poll();
  assert.equal(p.node('declaration-submit').hidden, true);
  assert.equal(p.node('declaration-activate').hidden, true);
  assert.match(p.node('declaration-message').textContent, /unconfirmed/);
  Object.assign(p.records[0], {stage: 'submitted', state: 'accepted', approved: true, checked_at: Date.now()/1000-31});
  await p.view.poll();
  assert.equal(p.node('declaration-activate').hidden, true);
});

test('outage clears status and disconnect clears personal and plan data', async () => {
  const p = page();
  await p.view.connect({declarations_enabled: true});
  await p.prepare(); await p.click('submit');
  p.outage(true);
  await p.view.poll();
  assert.equal(p.node('declaration-status').textContent, 'Unknown');
  assert.equal(p.node('declaration-activate').hidden, true);
  p.view.clear();
  assert.equal(p.node('declaration-summary').textContent, '');
  assert.equal(p.node('declaration-pilot').textContent, '');
  assert.equal(p.node('declaration-card').hidden, true);
});

test('Spanish status and recovery messages are available', async () => {
  const p = page({language: 'es'});
  await p.view.connect({declarations_enabled: true});
  await p.prepare(); await p.click('submit');
  assert.match(p.node('declaration-status').textContent, /Aceptada/);
  p.outage(true); await p.view.poll();
  assert.match(p.node('declaration-message').textContent, /no disponible/);
});
