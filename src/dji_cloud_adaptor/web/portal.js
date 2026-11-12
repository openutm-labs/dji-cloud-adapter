"use strict";
const text = {
  en: {
    firstTime: "First time on this controller? Use a setup code",
    enrollStep: "FIRST-TIME SETUP",
    enrollTitle: "Set up this controller",
    enrollBody: "Enter the setup code from your administrator. You only do this once: after that, this controller connects by itself.",
    invitationLabel: "Setup code",
    modelLabel: "Which aircraft is linked to this controller?",
    chooseModel: "Choose the aircraft that is linked to this controller.",
    nicknameLabel: "Controller nickname (optional)",
    enrollGround: "Keep the aircraft on the ground, powered on and linked to this controller.",
    register: "Connect →",
    backToConnect: "I have a connection code instead",
    saveCodeTitle: "Keep your connection code",
    saveCodeBody: "This code belongs to this controller. Save it privately for reconnecting later. Do not share it or include it in a screenshot.",
    showCode: "Show code",
    hideCode: "Hide code",
    invalid_invitation: "Check the setup code. Each code works once and expires; ask your administrator for a new one.",
    invitation_used: "This setup code was already used. Ask your administrator for a new one.",
    enrollment_session_expired: "Setup took too long. Enter the setup code again.",
    unsupported_model: "This aircraft model is not enabled for self-registration. Ask your administrator for its approved route.",
    equipment_identity_invalid: "Pilot 2 could not read two different equipment IDs. Check the aircraft link on the ground and retry.",
    equipment_already_registered: "This controller and aircraft are already registered. Ask your administrator to reconnect them; don't register them again.",
    enrollment_capacity: "The organisation’s registration limit was reached. Contact your administrator.",
    registration_pending: "Registration is saved, but the connection service is not ready yet. Keep this page open and tap Connect again to retry.",
    aircraftRequired: "Pilot 2 could not read the connected aircraft ID. Power on and link the supported aircraft on the ground, then retry.",
    device_revoked: "This device's access was revoked. Contact your administrator.",

    eyebrow: "DJI PILOT 2 CONNECTION",
    title: "Your flight. Connected.",
    intro:
      "Share aircraft telemetry with your organisation while you keep flying with DJI Pilot 2.",
    outsideTitle: "Open this page in DJI Pilot 2",
    outsideBody:
      "On your compatible controller, open Cloud Service → Open Platforms and enter this website’s address. This page cannot connect an aircraft from a regular browser.",
    step: "CONTROLLER SETUP",
    connectTitle: "Connect with a connection code",
    connectBody:
      "Enter the connection code from your administrator. You only need it once on this controller.",
    codeLabel: "Connection code",
    codeHelp:
      "This is the long code for this controller, not a setup code. Keep it private.",
    connect: "Connect →",
    connectionLabel: "CONNECTION STATUS",
    connectionDetails: "Details for your coordinator",
    controller: "Controller connection",
    aircraft: "Aircraft telemetry",
    blender: "Flight Blender",
    received: "Last aircraft sample",
    accepted: "Last API acceptance",
    pending: "Waiting to send",
    disconnect: "Disconnect and forget this controller",
    note: "Your pilot, flight permissions and operating checks remain part of your organisation’s normal procedure. No flight-control access is requested.",
    help: "Need help? Contact the administrator who gave you this link.",
    connecting: "Connecting…",
    connected: "Connected",
    waiting: "Waiting",
    stale: "Not recent",
    notConnected: "Not connected",
    acceptedState: "API accepted",
    pendingState: "Sending pending",
    unavailable: "Not configured",
    checking: "Checking…",
    offline: "Status unavailable",
    expired: "This controller is no longer connected. Set it up again with a new setup code from your administrator.",
    invalid_connection_code: "Check your connection code and try again.",
    wrong_controller:
      "This code belongs to another controller. Ask your administrator for the correct one.",
    dji_configuration_pending:
      "Your organisation’s DJI connection is not configured yet. Please contact your administrator.",
    try_later: "Too many attempts. Wait a minute, then try again.",
    invalid_fields: "Check the code and try again.",
    generic:
      "Could not connect. Check internet and ask your administrator if this continues.",
    licenseError:
      "DJI could not verify the application licence. Ask your administrator to check the DJI setup.",
    bridgeError:
      "Pilot 2 could not load the connection. Ask your administrator to check the supported controller and Pilot version.",
    sampleHelp:
      "Waiting for a recent position from an approved aircraft. Check its normal ground setup with your administrator.",
    activeHelp:
      "Recent telemetry is arriving. API acceptance confirms receipt by Blender’s API; your organisation still needs to verify the record in its dashboard.",
    backendHelp:
      "The Blender connection needs attention. Your administrator can check API credentials and server status.",
    nativeHelp:
      "Pilot 2 is still connecting to the telemetry service. Check internet and your organisation’s connection settings.",
    noSecret: "No connection code is saved in this browser.",
    reconnectTitle: "Reconnecting this controller…",
    reconnectFailed: "Couldn't reach OpenUTM. Check the controller's internet, then try again.",
    retry: "Try again",
    rememberedNote: "This controller is remembered. Next time, open this page and it connects by itself.",
    overallChecking: "Checking the connection…",
    overallCheckingDetail: "This takes a few seconds.",
    overallGood: "OpenUTM can see your drone",
    overallGoodDetail: "Last position shared at {time}",
    overallCatchingUp: "Connected: sending saved positions",
    overallCatchingUpDetail: "{count} positions waiting to send.",
    overallSending: "Connected: sending positions",
    overallSendingDetail: "Waiting for OpenUTM to confirm.",
    overallNoAircraft: "Connected: waiting for your drone",
    overallNoAircraftDetail: "Turn on the drone, keep it linked to this controller and wait for GPS.",
    overallConnecting: "Connecting to OpenUTM…",
    overallConnectingDetail: "Check that the controller has internet.",
    overallBackend: "Your drone isn't reaching OpenUTM",
    overallBackendDetail: "Tell your administrator the time and what you see here.",
    overallOffline: "Can't check the connection",
    overallOfflineDetail: "Check the controller's internet. Positions may still be sending.",
  },
  es: {
    firstTime: "¿Primera vez en este controlador? Use un código de configuración",
    enrollStep: "CONFIGURACIÓN INICIAL",
    enrollTitle: "Configure este controlador",
    enrollBody: "Introduzca el código de configuración que le dio el administrador. Solo se hace una vez: después, este controlador se conecta solo.",
    invitationLabel: "Código de configuración",
    modelLabel: "¿Qué aeronave está enlazada con este controlador?",
    chooseModel: "Elija la aeronave enlazada con este controlador.",
    nicknameLabel: "Nombre del controlador (opcional)",
    enrollGround: "Mantenga la aeronave en tierra, encendida y enlazada con este controlador.",
    register: "Conectar →",
    backToConnect: "Tengo un código de conexión",
    saveCodeTitle: "Conserve su código de conexión",
    saveCodeBody: "Este código pertenece a este controlador. Guárdelo de forma privada para reconectar. No lo comparta ni lo incluya en capturas.",
    showCode: "Mostrar código",
    hideCode: "Ocultar código",
    invalid_invitation: "Revise el código de configuración. Cada código sirve una vez y vence; pida uno nuevo al administrador.",
    invitation_used: "Este código de configuración ya se usó. Pida uno nuevo al administrador.",
    enrollment_session_expired: "La configuración tardó demasiado. Introduzca otra vez el código de configuración.",
    unsupported_model: "Este modelo no tiene autorregistro habilitado. Consulte su ruta aprobada con el administrador.",
    equipment_identity_invalid: "Pilot 2 no pudo leer dos identificadores distintos. Revise el enlace de la aeronave en tierra y reintente.",
    equipment_already_registered: "Este controlador y esta aeronave ya están registrados. Pida al administrador que los vuelva a conectar; no los registre otra vez.",
    enrollment_capacity: "Se alcanzó el límite de registros de la organización. Contacte con el administrador.",
    registration_pending: "El registro está guardado, pero el servicio de conexión aún no está listo. Mantenga esta página abierta y toque Conectar de nuevo.",
    aircraftRequired: "Pilot 2 no pudo leer el identificador de la aeronave. Encienda y enlace la aeronave compatible en tierra y reintente.",
    device_revoked: "Se revocó el acceso del dispositivo. Contacte con el administrador.",

    eyebrow: "CONEXIÓN CON DJI PILOT 2",
    title: "Su vuelo, conectado.",
    intro:
      "Comparta telemetría con su organización mientras sigue volando con DJI Pilot 2.",
    outsideTitle: "Abra esta página en DJI Pilot 2",
    outsideBody:
      "En el controlador compatible, abra Cloud Service → Open Platforms e introduzca la dirección de este sitio. Un navegador normal no puede conectar la aeronave desde esta página.",
    step: "CONFIGURACIÓN DEL CONTROLADOR",
    connectTitle: "Conectar con un código de conexión",
    connectBody:
      "Introduzca el código de conexión que le dio el administrador. Solo lo necesita una vez en este controlador.",
    codeLabel: "Código de conexión",
    codeHelp:
      "Es el código largo de este controlador, no un código de configuración. Manténgalo privado.",
    connect: "Conectar →",
    connectionLabel: "ESTADO DE LA CONEXIÓN",
    connectionDetails: "Detalles para su coordinador",
    controller: "Conexión del controlador",
    aircraft: "Telemetría de la aeronave",
    blender: "Flight Blender",
    received: "Última muestra de la aeronave",
    accepted: "Última aceptación de la API",
    pending: "Pendientes de envío",
    disconnect: "Desconectar y olvidar este controlador",
    note: "La identidad del piloto, los permisos y las revisiones siguen el procedimiento de la organización. No se solicita acceso al control de vuelo.",
    help: "¿Necesita ayuda? Contacte con el administrador que le dio este enlace.",
    connecting: "Conectando…",
    connected: "Conectado",
    waiting: "En espera",
    stale: "Sin datos recientes",
    notConnected: "Sin conexión",
    acceptedState: "API: aceptado",
    pendingState: "Envío pendiente",
    unavailable: "Sin configurar",
    checking: "Comprobando…",
    offline: "Estado no disponible",
    expired: "Este controlador ya no está conectado. Configúrelo otra vez con un nuevo código de configuración del administrador.",
    invalid_connection_code: "Compruebe el código e inténtelo de nuevo.",
    wrong_controller:
      "Este código es de otro controlador. Pida el correcto al administrador.",
    dji_configuration_pending:
      "La conexión DJI de la organización aún no está configurada. Contacte con el administrador.",
    try_later: "Demasiados intentos. Espere un minuto y vuelva a intentarlo.",
    invalid_fields: "Revise el código e inténtelo de nuevo.",
    generic:
      "No se pudo conectar. Compruebe internet y consulte al administrador si persiste.",
    licenseError:
      "DJI no pudo verificar la licencia. Pida al administrador que revise la configuración DJI.",
    bridgeError:
      "Pilot 2 no pudo cargar la conexión. Pida revisar el controlador compatible y la versión de Pilot.",
    sampleHelp:
      "Esperando una posición reciente de una aeronave aprobada. Revise su configuración normal en tierra con el administrador.",
    activeHelp:
      "Llegan datos recientes. La aceptación confirma recepción por la API de Blender; la organización debe verificar también el registro en su panel.",
    backendHelp:
      "La conexión con Blender necesita revisión. El administrador puede comprobar credenciales y estado del servidor.",
    nativeHelp:
      "Pilot 2 sigue conectando con el servicio. Compruebe internet y la configuración de la organización.",
    noSecret: "No se guarda el código en este navegador.",
    reconnectTitle: "Reconectando este controlador…",
    reconnectFailed: "No se pudo contactar con OpenUTM. Compruebe el internet del controlador y vuelva a intentarlo.",
    retry: "Reintentar",
    rememberedNote: "Este controlador queda recordado. La próxima vez, abra esta página y se conectará solo.",
    overallChecking: "Comprobando la conexión…",
    overallCheckingDetail: "Tarda unos segundos.",
    overallGood: "OpenUTM ve su dron",
    overallGoodDetail: "Última posición compartida a las {time}",
    overallCatchingUp: "Conectado: enviando posiciones guardadas",
    overallCatchingUpDetail: "{count} posiciones pendientes de envío.",
    overallSending: "Conectado: enviando posiciones",
    overallSendingDetail: "Esperando la confirmación de OpenUTM.",
    overallNoAircraft: "Conectado: esperando su dron",
    overallNoAircraftDetail: "Encienda el dron, manténgalo enlazado con este controlador y espere la señal GPS.",
    overallConnecting: "Conectando con OpenUTM…",
    overallConnectingDetail: "Compruebe que el controlador tenga internet.",
    overallBackend: "La posición de su dron no llega a OpenUTM",
    overallBackendDetail: "Indique al administrador la hora y lo que ve aquí.",
    overallOffline: "No se puede comprobar la conexión",
    overallOfflineDetail: "Compruebe el internet del controlador. Puede que las posiciones se sigan enviando.",
  },
};
let language = "en";
try {
  language = localStorage.getItem("language") === "es" ? "es" : "en";
} catch {
  /* Storage may be disabled in a controller WebView. */
}
// A remembered controller session. Pilot 2 keeps the same token in its API module; this copy
// covers a Pilot 2 restart that unloads that module. Cleared on disconnect or rejection.
const SESSION_KEY = "openutm.controllerSession";
let token = "",
  nativeConnected = false,
  currentStatus = null,
  statusFailed = false,
  timer = null;
let enrollmentToken = "",
  enrollmentEnabled = false;
const modelButtons = [];
const bridge = window.djiBridge;
const el = (id) => document.getElementById(id);
const t = (key) => text[language][key] || text[language].generic;
const fill = (key, values) =>
  t(key).replace(/\{(\w+)\}/g, (_, name) => String(values[name] ?? ""));
function translate() {
  document.documentElement.lang = language;
  document.title =
    language === "es"
      ? "OpenUTM · Conecte su controlador"
      : "OpenUTM · Connect your controller";
  el("language").value = language;
  document.querySelectorAll("[data-text]").forEach((node) => {
    node.textContent = t(node.dataset.text);
  });
  if (currentStatus) renderStatus(currentStatus);
  else if (!el("connection-card").hidden) renderOverall(null);
  declarations.translate();
}
function storedSession() {
  try {
    return localStorage.getItem(SESSION_KEY) || "";
  } catch {
    return "";
  }
}
function rememberSession(config) {
  try {
    if (config && config.remember && token) localStorage.setItem(SESSION_KEY, token);
    else localStorage.removeItem(SESSION_KEY);
  } catch {
    /* Storage may be disabled; Pilot 2 still keeps its own API token. */
  }
}
function forgetSession() {
  try {
    localStorage.removeItem(SESSION_KEY);
  } catch {
    /* Nothing stored. */
  }
}
function native(method, ...args) {
  if (!bridge || typeof bridge[method] !== "function")
    throw new Error("bridgeError");
  let value = bridge[method](...args);
  if (["platformGetRemoteControllerSN", "platformGetAircraftSN"].includes(method) &&
      typeof value === "string" && !value.trim().startsWith("{")) return value;
  if (typeof value === "string") {
    try {
      value = JSON.parse(value);
    } catch {
      if (!["platformGetRemoteControllerSN", "platformGetAircraftSN"].includes(method))
        throw new Error("bridgeError");
      // Some Pilot versions return the documented serial string directly.
    }
  }
  if (value && typeof value === "object" && "code" in value) {
    if (value.code !== 0) throw new Error("bridgeError");
    const data = value.data;
    if (
      [
        "platformVerifyLicense",
        "platformIsVerified",
        "thingGetConnectState",
        "platformIsComponentLoaded",
      ].includes(method)
    ) {
      return data && typeof data === "object" && Object.keys(data).length === 0
        ? true
        : data;
    }
    if (data === false && /^(platformSet|platformLoad)/.test(method))
      throw new Error("bridgeError");
    return data;
  }
  return value;
}
async function api(path, body, authToken = token) {
  const response = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const error = new Error(data.detail || "generic");
    error.status = response.status;
    throw error;
  }
  return response.json();
}
function badge(id, key, kind) {
  el(id).textContent = t(key);
  el(id).className = `badge ${kind || ""}`;
}
function freshness(status) {
  const sourceTime = status.last_observed_at || status.last_received_at;
  return {
    sourceTime,
    recent: Boolean(sourceTime && status.server_time - sourceTime < 30),
    accepted: Boolean(
      status.last_accepted_at && status.server_time - status.last_accepted_at < 30,
    ),
  };
}
function clock(seconds) {
  return new Date(seconds * 1000).toLocaleTimeString(language === "es" ? "es-PA" : "en", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}
function setOverall(kind, titleKey, detailKey, values = {}) {
  el("overall").className = `overall ${kind}`;
  el("overall-icon").textContent = kind === "good" ? "✓" : kind === "bad" ? "!" : "…";
  el("overall-title").textContent = t(titleKey);
  el("overall-detail").textContent = fill(detailKey, values);
}
// One plain-language answer for the pilot; the three technical rows stay under the details.
function renderOverall(status) {
  if (!status)
    return statusFailed
      ? setOverall("bad", "overallOffline", "overallOfflineDetail")
      : setOverall("wait", "overallChecking", "overallCheckingDetail");
  const { recent, accepted } = freshness(status);
  const pending = (status.counts && status.counts.pending) || 0;
  if (!status.blender_configured || status.last_error)
    return setOverall("bad", "overallBackend", "overallBackendDetail");
  if (!nativeConnected)
    return setOverall("wait", "overallConnecting", "overallConnectingDetail");
  if (!recent) return setOverall("wait", "overallNoAircraft", "overallNoAircraftDetail");
  if (pending)
    return setOverall("wait", "overallCatchingUp", "overallCatchingUpDetail", { count: pending });
  if (accepted)
    return setOverall("good", "overallGood", "overallGoodDetail", {
      time: clock(status.last_accepted_at),
    });
  return setOverall("wait", "overallSending", "overallSendingDetail");
}
function renderStatus(status) {
  const { sourceTime, recent, accepted } = freshness(status);
  badge(
    "controller-state",
    nativeConnected ? "connected" : "notConnected",
    nativeConnected ? "good" : "wait",
  );
  badge(
    "aircraft-state",
    recent ? "connected" : status.last_received_at ? "stale" : "waiting",
    recent ? "good" : "wait",
  );
  badge(
    "blender-state",
    !status.blender_configured
      ? "unavailable"
      : status.counts.pending
        ? "pendingState"
        : accepted
          ? "acceptedState"
          : "waiting",
    accepted && !status.counts.pending ? "good" : "wait",
  );
  const date = (v) =>
    v
      ? new Date(v * 1000).toLocaleString(language === "es" ? "es-PA" : "en", {
          month: "short",
          day: "numeric",
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          timeZoneName: "short",
        })
      : "—";
  el("last-received").textContent = date(sourceTime);
  el("last-accepted").textContent = date(status.last_accepted_at);
  el("pending-count").textContent = String(status.counts.pending || 0);
  el("status-help").textContent = t(
    !status.blender_configured || status.last_error
      ? "backendHelp"
      : !nativeConnected
        ? "nativeHelp"
        : recent
          ? "activeHelp"
          : "sampleHelp",
  );
  renderOverall(status);
}
window.onDjiCloudConnection = function (value) {
  try {
    if (typeof value === "string") value = JSON.parse(value);
    if (value && typeof value === "object") value = value.data;
    nativeConnected = value === true || value === 1;
  } catch {
    nativeConnected = false;
  }
  if (currentStatus) renderStatus(currentStatus);
};
async function poll() {
  try {
    if (bridge) window.onDjiCloudConnection(native("thingGetConnectState"));
    currentStatus = await api("/api/pilot/status");
    statusFailed = false;
    renderStatus(currentStatus);
    await declarations.poll();
  } catch (error) {
    if (error.status === 401) {
      await disconnect(false);
      showSetup("expired");
      return;
    }
    currentStatus = null;
    statusFailed = true;
    badge("aircraft-state", "offline", "wait");
    badge("blender-state", "offline", "wait");
    el("status-help").textContent = t("generic");
    renderOverall(null);
  }
}
// The first screen for a controller that is not connected: a setup code where self-registration
// is enabled, otherwise a connection code.
function showSetup(messageKey = "") {
  el("reconnect-card").hidden = true;
  el("connection-card").hidden = true;
  el("enrollment-card").hidden = !enrollmentEnabled;
  el("connect-card").hidden = enrollmentEnabled;
  if (messageKey)
    el(enrollmentEnabled ? "enrollment-message" : "message").textContent = t(messageKey);
}
function showConnection(config) {
  declarations.connect(config);
  el("device-name").textContent = config.device_name;
  el("workspace-name").textContent = config.workspace_name;
  el("remembered-note").hidden = !config.remember;
  el("reconnect-card").hidden = true;
  el("connect-card").hidden = true;
  el("enrollment-card").hidden = true;
  el("connection-card").hidden = false;
  currentStatus = null;
  statusFailed = false;
  renderOverall(null);
  if (timer) clearInterval(timer);
  poll();
  timer = setInterval(poll, 5000);
}
function configure(config) {
  native("platformSetWorkspaceId", config.workspace_id);
  native(
    "platformSetInformation",
    "OpenUTM",
    config.workspace_name,
    "Aircraft telemetry / Telemetría de aeronaves",
  );
  native(
    "platformLoadComponent",
    "api",
    JSON.stringify({ host: config.public_url, token }),
  );
  native(
    "platformLoadComponent",
    "thing",
    JSON.stringify({ ...config.mqtt, connectCallback: "onDjiCloudConnection" }),
  );
  rememberSession(config);
  showConnection(config);
}
async function disconnect(revoke = true) {
  declarations.clear();
  if (timer) clearInterval(timer);
  timer = null;
  if (bridge) {
    try {
      native("thingDisconnect");
    } catch {
      /* No aircraft control is involved. */
    }
    try {
      native("platformUnloadComponent", "thing");
    } catch {
      /* Already unloaded. */
    }
    try {
      native("apiSetToken", "");
    } catch {
      /* API module may not be loaded. */
    }
  }
  if (revoke && token) await api("/api/pilot/logout", {}).catch(() => {});
  forgetSession();
  token = "";
  el("new-code").value = "";
  el("new-code").type = "password";
  el("save-code-card").hidden = true;
  el("remembered-note").hidden = true;
  nativeConnected = false;
  currentStatus = null;
  statusFailed = false;
  el("reconnect-card").hidden = true;
  el("connect-card").hidden = false;
  el("connection-card").hidden = true;
  el("connect").disabled = !bridge;
  el("message").textContent = "";
}
el("connect-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!bridge) return;
  el("connect").disabled = true;
  el("message").textContent = t("connecting");
  try {
    const code = el("code").value.trim();
    el("code").value = "";
    const session = await api("/api/pilot/login", { code });
    token = session.token;
    const dji = await api("/api/pilot/bootstrap");
    if (
      native("platformVerifyLicense", dji.app_id, dji.app_key, dji.license) !==
      true
    )
      throw new Error("licenseError");
    const gateway_sn = native("platformGetRemoteControllerSN");
    const config = await api("/api/pilot/activate", { gateway_sn });
    configure(config);
    el("message").textContent = "";
  } catch (error) {
    await disconnect();
    el("message").textContent = t(error.message);
  } finally {
    el("connect").disabled = !bridge;
  }
});
el("disconnect").addEventListener("click", async () => {
  await disconnect();
  showSetup();
});
el("language").addEventListener("change", () => {
  language = el("language").value;
  try {
    localStorage.setItem("language", language);
  } catch {
    /* Optional preference only. */
  }
  translate();
});
// Reopen without typing: use the session Pilot 2 (or this page) remembered for this controller.
// Returns "connected", "retry" (kept for an outage), "expired" (rejected and forgotten) or "none".
async function resume() {
  if (!bridge) return "none";
  let saved = "";
  try {
    saved = native("apiGetToken");
  } catch {
    /* The API module is not loaded, for example after Pilot 2 restarted. */
  }
  if (typeof saved !== "string" || !saved) saved = storedSession();
  if (!saved) return "none";
  token = saved;
  el("connect-card").hidden = true;
  el("enrollment-card").hidden = true;
  el("reconnect-card").hidden = false;
  el("retry").hidden = true;
  el("reconnect-message").textContent = "";
  try {
    if (native("platformIsVerified") !== true) {
      const dji = await api("/api/pilot/bootstrap");
      if (native("platformVerifyLicense", dji.app_id, dji.app_key, dji.license) !== true)
        throw new Error("licenseError");
    }
    // Re-validate the physical controller before returning credentials on page reopen.
    const gateway_sn = native("platformGetRemoteControllerSN");
    const config = await api("/api/pilot/activate", { gateway_sn });
    if (native("thingGetConnectState") === true) {
      nativeConnected = true;
      rememberSession(config);
      showConnection(config);
    } else configure(config);
    return "connected";
  } catch (error) {
    if (error.status === 401 || error.status === 403) {
      await disconnect(false);
      return "expired";
    }
    // An outage must not cost the pilot their remembered controller: keep it and offer a retry.
    el("reconnect-message").textContent = t(
      ["licenseError", "bridgeError"].includes(error.message) ? error.message : "reconnectFailed",
    );
    el("retry").hidden = false;
    return "retry";
  }
}
async function reconnect() {
  const outcome = await resume();
  if (outcome === "expired") showSetup("expired");
  else if (outcome === "none" && !token) showSetup();
}
el("retry").addEventListener("click", () => reconnect());
const declarations = window.PilotDeclarations({
  api, language: () => language, aircraftSerial: () => {
    try { return native("platformGetAircraftSN"); } catch { return ""; }
  },
});
translate();
el("browser-notice").hidden = Boolean(bridge);
el("connect").disabled = !bridge;

// A setup code (invitation) is separate from both account sign-in and an existing controller code.
el("open-enrollment").addEventListener("click", () => {
  el("connect-card").hidden = true;
  el("enrollment-card").hidden = false;
});
el("cancel-enrollment").addEventListener("click", () => {
  el("connect-card").hidden = false;
  el("enrollment-card").hidden = true;
  el("enrollment-message").textContent = "";
});
el("show-new-code").addEventListener("click", () => {
  const show = el("new-code").type === "password";
  el("new-code").type = show ? "text" : "password";
  el("show-new-code").textContent = t(show ? "hideCode" : "showCode");
});
el("enrollment-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!bridge) return;
  if (!el("aircraft-model").value) {
    el("enrollment-message").textContent = t("chooseModel");
    return;
  }
  el("register").disabled = true;
  el("enrollment-message").textContent = t("connecting");
  let registered = false;
  try {
    if (!enrollmentToken) {
      const session = await api("/api/enrollment/start", {
        invitation_code: el("invitation").value.trim(),
      }, "");
      enrollmentToken = session.token;
      el("invitation").value = "";
      el("invitation").required = false;
    }
    const dji = await api("/api/enrollment/bootstrap", undefined, enrollmentToken);
    if (native("platformVerifyLicense", dji.app_id, dji.app_key, dji.license) !== true)
      throw new Error("licenseError");
    const gateway_sn = native("platformGetRemoteControllerSN");
    let aircraft_sn;
    try { aircraft_sn = native("platformGetAircraftSN"); }
    catch { throw new Error("aircraftRequired"); }
    if (typeof aircraft_sn !== "string" || !aircraft_sn.trim())
      throw new Error("aircraftRequired");
    const result = await api("/api/enrollment/complete", {
      gateway_sn, aircraft_sn,
      aircraft_model: el("aircraft-model").value,
      name: el("controller-name").value.trim(),
    }, enrollmentToken);
    token = result.token;
    registered = true;
    el("new-code").value = result.connection_code;
    // A remembered controller reconnects by itself, so there is nothing for the pilot to keep.
    el("save-code-card").hidden = Boolean(result.config && result.config.remember);
    enrollmentToken = "";
    configure(result.config);
    el("enrollment-message").textContent = "";
  } catch (error) {
    if (error.status === 401) {
      enrollmentToken = "";
      el("invitation").required = true;
    }
    // Retain the temporary enrollment session on a provisioning outage, allowing safe retries.
    if (registered) {
      el("enrollment-card").hidden = true;
      el("connection-card").hidden = true;
      el("connect-card").hidden = false;
      el("save-code-card").hidden = false;
      el("code").value = el("new-code").value;
      el("message").textContent = t(error.message);
    } else el("enrollment-message").textContent = t(error.message);
  } finally {
    el("register").disabled = !bridge;
  }
});
function chooseModel(model) {
  el("aircraft-model").value = model;
  for (const [name, button] of modelButtons)
    button.setAttribute("aria-pressed", String(name === model));
}
async function enrollmentOptions() {
  try {
    const options = await api("/api/enrollment/options", undefined, "");
    if (!options || !options.enabled) return;
    const models = Array.isArray(options.models) ? options.models : [];
    if (models.length === 1) {
      // Nothing to ask when the organisation accepts a single model.
      el("aircraft-model").value = models[0];
      el("model-field").hidden = true;
    } else
      for (const model of models) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "choice";
        button.textContent = model;
        button.setAttribute("aria-pressed", "false");
        button.addEventListener("click", () => chooseModel(model));
        modelButtons.push([model, button]);
        el("model-choices").appendChild(button);
      }
    enrollmentEnabled = true;
    el("open-enrollment").hidden = false;
  } catch { /* Existing device-code connections remain available if options cannot load. */ }
}
el("register").disabled = !bridge;
(async () => {
  await enrollmentOptions();
  await reconnect();
})();
