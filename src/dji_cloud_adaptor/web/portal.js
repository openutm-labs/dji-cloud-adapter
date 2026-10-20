"use strict";
const text = {
  en: {
    firstTime: "First time here? Register this controller",
    enrollStep: "FIRST-TIME SETUP",
    enrollTitle: "Register your equipment",
    enrollBody: "Use your private registration invitation. Pilot 2 reads the connected controller and aircraft IDs; you do not need to send serial numbers in advance.",
    invitationLabel: "Invitation code",
    modelLabel: "Aircraft model",
    chooseModel: "Choose your aircraft",
    nicknameLabel: "Controller nickname (optional)",
    enrollGround: "Keep the aircraft on the ground, powered on and linked to this controller. One invitation registers one controller and its aircraft.",
    register: "Register and connect →",
    backToConnect: "I already have a connection code",
    saveCodeTitle: "Keep your connection code",
    saveCodeBody: "This code belongs to this controller. Save it privately for reconnecting later. Do not share it or include it in a screenshot.",
    showCode: "Show code",
    hideCode: "Hide code",
    invalid_invitation: "Check your invitation code and its expiry with your administrator.",
    invitation_used: "This invitation has already registered a controller. Use its saved connection code or ask your administrator for help.",
    enrollment_session_expired: "Setup expired. Enter your invitation again; if registration completed, use the saved connection code.",
    unsupported_model: "This aircraft model is not enabled for self-registration. Ask your administrator for its approved route.",
    equipment_identity_invalid: "Pilot 2 could not read two different equipment IDs. Check the aircraft link on the ground and retry.",
    equipment_already_registered: "This equipment is already registered. Use its existing connection code or contact your administrator; do not register it under another identity.",
    enrollment_capacity: "The organisation’s registration limit was reached. Contact your administrator.",
    registration_pending: "Registration is saved, but the connection service is not ready yet. Keep this page open and tap Register and connect again to retry.",
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
    connectTitle: "Connect to your organisation",
    connectBody:
      "Already registered? Use this controller’s saved connection code. For first-time setup, choose Register this controller below.",
    codeLabel: "Connection code",
    codeHelp:
      "Use the saved controller code here, not a registration invitation or account password. Keep it private.",
    connect: "Connect telemetry →",
    connectionLabel: "CONNECTION STATUS",
    controller: "Controller connection",
    aircraft: "Aircraft telemetry",
    blender: "Flight Blender",
    received: "Last aircraft sample",
    accepted: "Last API acceptance",
    pending: "Waiting to send",
    disconnect: "Disconnect this controller",
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
    expired: "Your session ended. Enter the connection code again.",
    invalid_connection_code: "Check your connection code and try again.",
    wrong_controller:
      "This code belongs to another controller. Ask your administrator for the correct one.",
    dji_configuration_pending:
      "Your organisation’s DJI connection is not configured yet. Please contact your administrator.",
    try_later: "Too many attempts. Wait a minute, then try again.",
    invalid_fields: "Check your connection code and try again.",
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
  },
  es: {
    firstTime: "¿Primera vez? Registre este controlador",
    enrollStep: "CONFIGURACIÓN INICIAL",
    enrollTitle: "Registre su equipo",
    enrollBody: "Use la invitación privada de la organización. Pilot 2 lee los identificadores del controlador y la aeronave conectados; no necesita enviar números de serie previamente.",
    invitationLabel: "Código de invitación",
    modelLabel: "Modelo de aeronave",
    chooseModel: "Elija su aeronave",
    nicknameLabel: "Nombre del controlador (opcional)",
    enrollGround: "Mantenga la aeronave en tierra, encendida y enlazada con este controlador. Cada invitación registra un controlador y su aeronave.",
    register: "Registrar y conectar →",
    backToConnect: "Ya tengo un código de conexión",
    saveCodeTitle: "Conserve su código de conexión",
    saveCodeBody: "Este código pertenece a este controlador. Guárdelo de forma privada para reconectar. No lo comparta ni lo incluya en capturas.",
    showCode: "Mostrar código",
    hideCode: "Ocultar código",
    invalid_invitation: "Compruebe el código de invitación y su vencimiento con el administrador.",
    invitation_used: "Esta invitación ya registró un controlador. Use su código de conexión guardado o consulte al administrador.",
    enrollment_session_expired: "La configuración venció. Introduzca otra vez la invitación; si terminó el registro, use el código de conexión guardado.",
    unsupported_model: "Este modelo no tiene autorregistro habilitado. Consulte su ruta aprobada con el administrador.",
    equipment_identity_invalid: "Pilot 2 no pudo leer dos identificadores distintos. Revise el enlace de la aeronave en tierra y reintente.",
    equipment_already_registered: "El equipo ya está registrado. Use su código existente o consulte al administrador; no lo registre con otra identidad.",
    enrollment_capacity: "Se alcanzó el límite de registros de la organización. Contacte con el administrador.",
    registration_pending: "El registro está guardado, pero el servicio de conexión aún no está listo. Mantenga esta página abierta y toque Registrar y conectar de nuevo.",
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
    connectTitle: "Conecte con su organización",
    connectBody:
      "¿Ya está registrado? Use el código guardado de este controlador. Para la primera vez, elija Registre este controlador abajo.",
    codeLabel: "Código de conexión",
    codeHelp:
      "Use aquí el código guardado, no la invitación ni la contraseña de su cuenta. Manténgalo privado.",
    connect: "Conectar telemetría →",
    connectionLabel: "ESTADO DE LA CONEXIÓN",
    controller: "Conexión del controlador",
    aircraft: "Telemetría de la aeronave",
    blender: "Flight Blender",
    received: "Última muestra de la aeronave",
    accepted: "Última aceptación de la API",
    pending: "Pendientes de envío",
    disconnect: "Desconectar este controlador",
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
    expired: "La sesión terminó. Introduzca el código de conexión otra vez.",
    invalid_connection_code: "Compruebe el código e inténtelo de nuevo.",
    wrong_controller:
      "Este código es de otro controlador. Pida el correcto al administrador.",
    dji_configuration_pending:
      "La conexión DJI de la organización aún no está configurada. Contacte con el administrador.",
    try_later: "Demasiados intentos. Espere un minuto y vuelva a intentarlo.",
    invalid_fields: "Compruebe el código e inténtelo de nuevo.",
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
  },
};
let language = "en";
try {
  language = localStorage.getItem("language") === "es" ? "es" : "en";
} catch {
  /* Storage may be disabled in a controller WebView. */
}
let token = "",
  nativeConnected = false,
  currentStatus = null,
  timer = null;
let enrollmentToken = "";
const bridge = window.djiBridge;
const el = (id) => document.getElementById(id);
const t = (key) => text[language][key] || text[language].generic;
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
  declarations.translate();
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
function renderStatus(status) {
  const sourceTime = status.last_observed_at || status.last_received_at;
  const recent = sourceTime && status.server_time - sourceTime < 30;
  const accepted =
    status.last_accepted_at &&
    status.server_time - status.last_accepted_at < 30;
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
    renderStatus(currentStatus);
    await declarations.poll();
  } catch (error) {
    if (error.status === 401) {
      await disconnect(false);
      el("message").textContent = t("expired");
      return;
    }
    badge("aircraft-state", "offline", "wait");
    badge("blender-state", "offline", "wait");
    el("status-help").textContent = t("generic");
  }
}
function showConnection(config) {
  declarations.connect(config);
  el("device-name").textContent = config.device_name;
  el("workspace-name").textContent = config.workspace_name;
  el("connect-card").hidden = true;
  el("enrollment-card").hidden = true;
  el("connection-card").hidden = false;
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
  token = "";
  el("new-code").value = "";
  el("new-code").type = "password";
  el("save-code-card").hidden = true;
  nativeConnected = false;
  currentStatus = null;
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
el("disconnect").addEventListener("click", () => disconnect());
el("language").addEventListener("change", () => {
  language = el("language").value;
  try {
    localStorage.setItem("language", language);
  } catch {
    /* Optional preference only. */
  }
  translate();
});
async function resume() {
  if (!bridge) return;
  try {
    if (native("platformIsVerified") !== true) return;
    const existing = native("apiGetToken");
    if (typeof existing !== "string" || !existing) return;
    token = existing;
    // Re-validate the physical controller before returning credentials on page reopen.
    const gateway_sn = native("platformGetRemoteControllerSN");
    const config = await api("/api/pilot/activate", { gateway_sn });
    if (native("thingGetConnectState") === true) {
      nativeConnected = true;
      showConnection(config);
    } else configure(config);
  } catch {
    await disconnect();
  }
}
const declarations = window.PilotDeclarations({
  api, language: () => language, aircraftSerial: () => {
    try { return native("platformGetAircraftSN"); } catch { return ""; }
  },
});
translate();
el("browser-notice").hidden = Boolean(bridge);
el("connect").disabled = !bridge;
resume();

// A registration invitation is separate from both account sign-in and an existing controller code.
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
    el("save-code-card").hidden = false;
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
      el("code").value = el("new-code").value;
      el("message").textContent = t(error.message);
    } else el("enrollment-message").textContent = t(error.message);
  } finally {
    el("register").disabled = !bridge;
  }
});
async function enrollmentOptions() {
  try {
    const options = await api("/api/enrollment/options", undefined, "");
    if (!options || !options.enabled) return;
    for (const model of options.models) {
      const option = document.createElement("option");
      option.value = model;
      option.textContent = model;
      el("aircraft-model").appendChild(option);
    }
    el("open-enrollment").hidden = false;
  } catch { /* Existing device-code connections remain available if options cannot load. */ }
}
el("register").disabled = !bridge;
enrollmentOptions();
