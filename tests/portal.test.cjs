const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(
  path.join(__dirname, "../src/dji_cloud_adaptor/web/portal.js"),
  "utf8",
);
function portal({
  outside = false,
  license = true,
  activation = 200,
  loadFailure = false,
  storageFailure = false,
  enrollment = false,
  aircraft = "NEW-AIRCRAFT-001",
  rawSerials = false,
  enrollmentFailures = 0,
  remember = undefined,
  models = ["Mavic 3 Enterprise", "Matrice 400"],
  apiToken = undefined,
  stored = {},
  verified = false,
  statusBody = undefined,
} = {}) {
  const nodes = new Map(),
    calls = [],
    nativeCalls = [];
  const node = (id) => {
    if (!nodes.has(id))
      nodes.set(id, {
        id,
        hidden: false,
        value: "",
        textContent: "",
        className: "",
        disabled: false,
        listeners: {},
        appendChild(child) {
          (this.children ||= []).push(child);
        },
        setAttribute(name, value) { (this.attributes ||= {})[name] = value; },
        addEventListener(name, fn) {
          this.listeners[name] = fn;
        },
      });
    return nodes.get(id);
  };
  const wrap = (data) => JSON.stringify({ code: 0, data });
  const config = {
    public_url: "https://example.org",
    workspace_id: "00000000-0000-0000-0000-000000000001",
    workspace_name: "Test workspace",
    device_name: "Test controller",
    mqtt: {
      host: "wss://example.org/mqtt",
      username: "pilot",
      password: "test-only",
    },
    ...(remember === undefined ? {} : { remember }),
  };
  const storage = new Map(Object.entries(stored));
  const context = {
    document: {
      documentElement: { lang: "en", classList: {toggle() {}} },
      getElementById: node,
      createElement: () => ({
        value: "", textContent: "", listeners: {},
        setAttribute(name, value) { (this.attributes ||= {})[name] = value; },
        addEventListener(name, fn) { this.listeners[name] = fn; },
      }),
      querySelectorAll: () => [],
    },
    localStorage: {
      getItem(key) {
        if (storageFailure) throw new Error();
        return storage.has(key) ? storage.get(key) : null;
      },
      setItem(key, value) {
        if (storageFailure) throw new Error();
        storage.set(key, value);
      },
      removeItem(key) {
        if (storageFailure) throw new Error();
        storage.delete(key);
      },
    },
    setInterval: () => 1,
    clearInterval: () => {},
    window: {},
    console,
    fetch: async (url, options) => {
      calls.push({ url, options });
      const responses = {
        "/api/enrollment/options": {enabled: enrollment, models},
        "/api/enrollment/start": {token: "enrollment-session"},
        "/api/enrollment/bootstrap": {app_id: "test-app", app_key: "test-key", license: "test-license"},
        "/api/enrollment/complete": {token: "new-device-session", connection_code: "private-new-device-code", config},
        "/api/pilot/login": { token: "session-token" },
        "/api/pilot/bootstrap": {
          app_id: "test-app",
          app_key: "test-key",
          license: "test-license",
        },
        "/api/pilot/activate": config,
        "/api/pilot/status": statusBody || {
          counts: { accepted: 1 },
          device_name: "Test controller",
          workspace_name: "Test workspace",
          server_time: 100,
          last_received_at: 99,
          last_accepted_at: 99,
          blender_configured: true,
        },
        "/api/pilot/logout": { status: "signed_out" },
      };
      if (url === "/api/pilot/activate" && activation === "offline") throw new Error("offline");
      const status = url === "/api/pilot/activate" ? activation :
        url === "/api/enrollment/complete" && enrollmentFailures-- > 0 ? 503 : 200;
      return {
        ok: status === 200,
        status,
        json: async () =>
          status === 200 ? responses[url] : { detail: status === 503 ? "registration_pending" : "wrong_controller" },
      };
    },
  };
  if (!outside)
    context.window.djiBridge = {
      platformVerifyLicense(...args) {
        nativeCalls.push(["license", ...args]);
        return wrap(license);
      },
      platformIsVerified() {
        return wrap(verified);
      },
      platformGetRemoteControllerSN() {
        return rawSerials ? "EXAMPLE-RC-001" : wrap("EXAMPLE-RC-001");
      },
      platformGetAircraftSN() {
        return rawSerials ? aircraft : wrap(aircraft);
      },
      platformSetWorkspaceId() {
        return wrap("");
      },
      platformSetInformation() {
        return wrap(true);
      },
      platformLoadComponent(name, param) {
        nativeCalls.push(["load", name, JSON.parse(param)]);
        return wrap(loadFailure ? false : "");
      },
      thingGetConnectState() {
        return wrap(true);
      },
      thingDisconnect() {
        return wrap("");
      },
      platformUnloadComponent() {
        return wrap("");
      },
      apiSetToken() {
        return wrap("");
      },
      ...(apiToken === undefined ? {} : { apiGetToken: () => wrap(apiToken) }),
    };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(__dirname, "../src/dji_cloud_adaptor/web/planning-map.js"), "utf8"), context);
  vm.runInContext(fs.readFileSync(path.join(__dirname, "../src/dji_cloud_adaptor/web/declarations.js"), "utf8"), context);
  vm.runInContext(source, context);
  return {
    node,
    calls,
    nativeCalls,
    context,
    storage,
    async settle() {
      for (let i = 0; i < 5; i++) await new Promise(setImmediate);
    },
    async register() {
      await new Promise(setImmediate);
      node("invitation").value = "private-invitation";
      node("aircraft-model").value = "Matrice 400";
      node("controller-name").value = "My controller";
      await node("enrollment-form").listeners.submit({ preventDefault() {} });
      await new Promise(setImmediate);
    },
    async connect() {
      node("code").value = "private-code";
      await node("connect-form").listeners.submit({ preventDefault() {} });
      await new Promise(setImmediate);
    },
  };
}

test("regular browser explains Pilot 2 and cannot connect", () => {
  const p = portal({ outside: true });
  assert.equal(p.node("browser-notice").hidden, false);
  assert.equal(p.node("connect").disabled, true);
});
test("documented bridge sequence verifies licence and controller before MQTT", async () => {
  const p = portal();
  await p.connect();
  assert.equal(p.nativeCalls[0][0], "license");
  assert.deepEqual(
    p.nativeCalls.filter((c) => c[0] === "load").map((c) => c[1]),
    ["api", "thing"],
  );
  const thing = p.nativeCalls.find((c) => c[1] === "thing");
  assert.equal(thing[2].connectCallback, "onDjiCloudConnection");
  assert.equal(p.node("connection-card").hidden, false);
  assert.equal(p.node("code").value, "");
  assert.equal(p.node("aircraft-state").textContent, "Connected");
  assert.equal(p.node("blender-state").textContent, "API accepted");
  assert(
    !p.nativeCalls.some((c) =>
      ["mission", "media", "drc", "liveshare"].includes(c[1]),
    ),
  );
});
test("failed licence never loads MQTT", async () => {
  const p = portal({ license: false });
  await p.connect();
  assert(!p.nativeCalls.some((c) => c[0] === "load"));
  assert.match(p.node("message").textContent, /licence/);
});
test("wrong controller cannot obtain MQTT connection", async () => {
  const p = portal({ activation: 403 });
  await p.connect();
  assert(!p.nativeCalls.some((c) => c[0] === "load"));
  assert.match(p.node("message").textContent, /another controller/);
});
test("component loading failure is not presented as connection success", async () => {
  const p = portal({ loadFailure: true });
  await p.connect();
  assert.equal(p.node("connection-card").hidden, true);
  assert.match(p.node("message").textContent, /could not load/);
});
test("restricted WebView storage does not break connection page", async () => {
  const p = portal({ storageFailure: true });
  await p.connect();
  assert.equal(p.node("connection-card").hidden, false);
});
test("status outage removes stale green aircraft and Blender badges", async () => {
  const p = portal();
  await p.connect();
  p.context.fetch = async () => {
    throw new Error("offline");
  };
  await p.context.poll();
  assert.equal(p.node("aircraft-state").textContent, "Status unavailable");
  assert.equal(p.node("blender-state").textContent, "Status unavailable");
});
test("native boolean success with an empty data object matches DJI demo semantics", async () => {
  const p = portal({ license: {} });
  await p.connect();
  assert.equal(p.node("connection-card").hidden, false);
});

test("source sample age takes priority over recent server receipt", async () => {
  const p = portal();
  const original = p.context.fetch;
  p.context.fetch = async (url, options) =>
    url === "/api/pilot/status"
      ? {
          ok: true,
          status: 200,
          json: async () => ({
            counts: {},
            server_time: 100,
            last_received_at: 99,
            last_observed_at: 20,
            blender_configured: true,
          }),
        }
      : original(url, options);
  await p.connect();
  assert.equal(p.node("aircraft-state").textContent, "Not recent");
});

test("self registration reads both IDs and saves the private device code", async () => {
  const p = portal({enrollment: true, rawSerials: true});
  await p.register();
  const completion = p.calls.find(c => c.url === "/api/enrollment/complete");
  assert.deepEqual(JSON.parse(completion.options.body), {
    gateway_sn: "EXAMPLE-RC-001", aircraft_sn: "NEW-AIRCRAFT-001",
    aircraft_model: "Matrice 400", name: "My controller",
  });
  assert.equal(p.node("invitation").value, "");
  assert.equal(p.node("new-code").value, "private-new-device-code");
  assert.equal(p.node("save-code-card").hidden, false);
  assert.equal(p.node("connection-card").hidden, false);
});
test("self registration requires the connected aircraft and a valid licence", async () => {
  for (const options of [{aircraft: ""}, {license: false}]) {
    const p = portal({enrollment: true, ...options});
    await p.register();
    assert(!p.calls.some(c => c.url === "/api/enrollment/complete"));
    assert(!p.nativeCalls.some(c => c[0] === "load"));
    assert(p.node("enrollment-message").textContent.length > 0);
  }
});
test("provisioning retry reuses the enrollment session", async () => {
  const p = portal({enrollment: true, enrollmentFailures: 1});
  await p.register();
  assert.match(p.node("enrollment-message").textContent, /Registration is saved/);
  assert(!p.nativeCalls.some(c => c[0] === "load"));
  await p.register();
  assert.equal(p.calls.filter(c => c.url === "/api/enrollment/start").length, 1);
  assert.equal(p.node("connection-card").hidden, false);
});
test("ordinary browser cannot self register", async () => {
  const p = portal({enrollment: true, outside: true});
  await p.register();
  assert.equal(p.node("register").disabled, true);
  assert(!p.calls.some(c => c.url === "/api/enrollment/start"));
});
test("connection failure after registration preserves the recovery code", async () => {
  const p = portal({enrollment: true, loadFailure: true});
  await p.register();
  assert.equal(p.node("connection-card").hidden, true);
  assert.equal(p.node("connect-card").hidden, false);
  assert.equal(p.node("code").value, "private-new-device-code");
  assert.equal(p.node("save-code-card").hidden, false);
});

const SESSION_KEY = "openutm.controllerSession";

test("a remembered controller reconnects without any code, even after Pilot 2 restarts", async () => {
  const p = portal({ apiToken: "remembered-session", remember: true });
  await p.settle();
  const urls = p.calls.map((c) => c.url);
  assert(!urls.includes("/api/pilot/login"));
  assert(urls.includes("/api/pilot/bootstrap"), "licence is verified again when Pilot 2 lost it");
  assert.equal(p.nativeCalls[0][0], "license");
  const activate = p.calls.find((c) => c.url === "/api/pilot/activate");
  assert.equal(activate.options.headers.Authorization, "Bearer remembered-session");
  assert.equal(p.node("connection-card").hidden, false);
  assert.equal(p.node("remembered-note").hidden, false);
  assert.equal(p.storage.get(SESSION_KEY), "remembered-session");
});
test("the page's own copy reconnects when Pilot 2's API token is gone", async () => {
  const p = portal({ stored: { [SESSION_KEY]: "stored-session" }, remember: true, verified: true });
  await p.settle();
  const activate = p.calls.find((c) => c.url === "/api/pilot/activate");
  assert.equal(activate.options.headers.Authorization, "Bearer stored-session");
  assert(!p.calls.some((c) => c.url === "/api/pilot/bootstrap"), "no licence call when still verified");
  assert.equal(p.node("connection-card").hidden, false);
});
test("an outage keeps the remembered controller and offers a retry", async () => {
  const p = portal({ apiToken: "remembered-session", activation: "offline", verified: true });
  await p.settle();
  assert.equal(p.node("reconnect-card").hidden, false);
  assert.equal(p.node("retry").hidden, false);
  assert.match(p.node("reconnect-message").textContent, /internet/);
  assert(!p.calls.some((c) => c.url === "/api/pilot/logout"));
  assert(!p.nativeCalls.some((c) => c[0] === "load"));
});
test("a rejected remembered session is forgotten and setup is shown", async () => {
  const p = portal({
    stored: { [SESSION_KEY]: "revoked-session" }, activation: 401, verified: true, enrollment: true,
  });
  await p.settle();
  assert.equal(p.storage.has(SESSION_KEY), false);
  assert.equal(p.node("enrollment-card").hidden, false);
  assert.equal(p.node("connect-card").hidden, true);
  assert.match(p.node("enrollment-message").textContent, /setup code/);
});
test("with self-registration on, a new controller opens on the setup-code screen", async () => {
  const p = portal({ enrollment: true });
  await p.settle();
  assert.equal(p.node("enrollment-card").hidden, false);
  assert.equal(p.node("connect-card").hidden, true);
  assert.equal(p.node("open-enrollment").hidden, false);
});
test("without self-registration, a new controller opens on the connection-code screen", async () => {
  const p = portal();
  await p.settle();
  assert.equal(p.node("connect-card").hidden, false);
  assert.equal(p.node("enrollment-card").hidden, true);
});
test("one accepted model is chosen for the pilot", async () => {
  const p = portal({ enrollment: true, models: ["Matrice 400"] });
  await p.settle();
  assert.equal(p.node("model-field").hidden, true);
  assert.equal(p.node("aircraft-model").value, "Matrice 400");
  assert.equal((p.node("model-choices").children || []).length, 0);
});
test("several models are one tap each, and registration waits for a choice", async () => {
  const p = portal({ enrollment: true });
  await p.settle();
  const buttons = p.node("model-choices").children;
  assert.deepEqual(buttons.map((b) => b.textContent), ["Mavic 3 Enterprise", "Matrice 400"]);
  p.node("invitation").value = "ABCD-2345";
  await p.node("enrollment-form").listeners.submit({ preventDefault() {} });
  assert.match(p.node("enrollment-message").textContent, /Choose the aircraft/);
  assert(!p.calls.some((c) => c.url === "/api/enrollment/start"));
  buttons[1].listeners.click();
  assert.equal(p.node("aircraft-model").value, "Matrice 400");
  assert.equal(buttons[1].attributes["aria-pressed"], "true");
  assert.equal(buttons[0].attributes["aria-pressed"], "false");
});
test("a remembered registration has no code to keep", async () => {
  const p = portal({ enrollment: true, remember: true });
  await p.register();
  assert.equal(p.node("save-code-card").hidden, true);
  assert.equal(p.node("connection-card").hidden, false);
  assert.equal(p.storage.get(SESSION_KEY), "new-device-session");
});
test("disconnecting forgets the controller", async () => {
  const p = portal({ remember: true });
  await p.connect();
  assert.equal(p.storage.get(SESSION_KEY), "session-token");
  await p.node("disconnect").listeners.click();
  assert.equal(p.storage.has(SESSION_KEY), false);
  assert(p.calls.some((c) => c.url === "/api/pilot/logout"));
});
test("one plain status says the drone is visible", async () => {
  const p = portal();
  await p.connect();
  await p.settle();
  assert.equal(p.node("overall-title").textContent, "OpenUTM can see your drone");
  assert.match(p.node("overall-detail").textContent, /Last position shared at/);
  assert.equal(p.node("overall").className, "overall good");
});
test("plain status asks for the drone when no recent position arrives", async () => {
  const p = portal({
    statusBody: { counts: {}, server_time: 100, last_received_at: 20, blender_configured: true },
  });
  await p.connect();
  await p.settle();
  assert.equal(p.node("overall-title").textContent, "Connected: waiting for your drone");
  assert.equal(p.node("overall").className, "overall wait");
});
test("plain status points to the administrator for a server-side fault", async () => {
  const p = portal({
    statusBody: { counts: { pending: 4 }, server_time: 100, last_received_at: 99, blender_configured: true, last_error: "http_503" },
  });
  await p.connect();
  await p.settle();
  assert.equal(p.node("overall-title").textContent, "Your drone isn't reaching OpenUTM");
  assert.equal(p.node("overall").className, "overall bad");
});
test("plain status reports when the connection cannot be checked", async () => {
  const p = portal();
  await p.connect();
  p.context.fetch = async () => {
    throw new Error("offline");
  };
  await p.context.poll();
  assert.equal(p.node("overall-title").textContent, "Can't check the connection");
});
test("plain status is translated", async () => {
  const p = portal();
  await p.connect();
  await p.settle();
  p.node("language").value = "es";
  p.node("language").listeners.change();
  assert.equal(p.node("overall-title").textContent, "OpenUTM ve su dron");
});
