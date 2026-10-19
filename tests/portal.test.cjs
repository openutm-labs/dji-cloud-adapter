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
    workspace_name: "Test lab",
    device_name: "Test controller",
    mqtt: {
      host: "wss://example.org/mqtt",
      username: "pilot",
      password: "test-only",
    },
  };
  const context = {
    document: {
      documentElement: { lang: "en" },
      getElementById: node,
      createElement: () => ({value: "", textContent: ""}),
      querySelectorAll: () => [],
    },
    localStorage: {
      getItem() {
        if (storageFailure) throw new Error();
        return null;
      },
      setItem() {},
    },
    setInterval: () => 1,
    clearInterval: () => {},
    window: {},
    console,
    fetch: async (url, options) => {
      calls.push({ url, options });
      const responses = {
        "/api/enrollment/options": {enabled: enrollment, models: ["Mavic 3 Enterprise", "Matrice 400"]},
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
        "/api/pilot/status": {
          counts: { accepted: 1 },
          device_name: "Test controller",
          workspace_name: "Test lab",
          server_time: 100,
          last_received_at: 99,
          last_accepted_at: 99,
          blender_configured: true,
        },
        "/api/pilot/logout": { status: "signed_out" },
      };
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
        return wrap(false);
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
    };
  vm.createContext(context);
  vm.runInContext(source, context);
  return {
    node,
    calls,
    nativeCalls,
    context,
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
