"use strict";
const text = {
  en: {
    eyebrow: "DJI PILOT 2 CONNECTION",
    title: "Your flight. Connected.",
    intro:
      "Share aircraft telemetry with your Flying Lab while you keep flying with DJI Pilot 2.",
    outsideTitle: "Open this page in DJI Pilot 2",
    outsideBody:
      "On your compatible controller, open Cloud Service → Open Platforms and enter this website’s address. This page cannot connect an aircraft from a regular browser.",
    step: "CONTROLLER SETUP",
    connectTitle: "Connect to your lab",
    connectBody:
      "Use the private connection code your coordinator gave you for this controller.",
    codeLabel: "Connection code",
    codeHelp:
      "This is a controller setup code, not your Passport password. Keep it private.",
    connect: "Connect telemetry →",
    connectionLabel: "CONNECTION STATUS",
    controller: "Controller connection",
    aircraft: "Aircraft telemetry",
    blender: "Flight Blender",
    received: "Last aircraft sample",
    accepted: "Last API acceptance",
    pending: "Waiting to send",
    disconnect: "Disconnect this controller",
    note: "Telemetry connection only. Your pilot, flight permissions and operating checks remain part of your lab’s normal procedure. No flight-control access is requested.",
    help: "Need help? Contact the coordinator who gave you this link.",
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
      "This code belongs to another controller. Ask your coordinator for the correct one.",
    dji_configuration_pending:
      "Your lab’s DJI connection is not configured yet. Please contact your coordinator.",
    try_later: "Too many attempts. Wait a minute, then try again.",
    invalid_fields: "Check your connection code and try again.",
    generic:
      "Could not connect. Check internet and ask your coordinator if this continues.",
    licenseError:
      "DJI could not verify the application licence. Ask your coordinator to check the DJI setup.",
    bridgeError:
      "Pilot 2 could not load the connection. Ask your coordinator to check the supported controller and Pilot version.",
    sampleHelp:
      "Waiting for a recent position from an approved aircraft. Check its normal ground setup with your coordinator.",
    activeHelp:
      "Recent telemetry is arriving. API acceptance confirms receipt by Blender’s API; your lab still needs to verify the record in its dashboard.",
    backendHelp:
      "The Blender connection needs attention. Your coordinator can check API credentials and server status.",
    nativeHelp:
      "Pilot 2 is still connecting to the telemetry service. Check internet and your lab’s connection settings.",
    noSecret: "No connection code is saved in this browser.",
  },
  es: {
    eyebrow: "CONEXIÓN CON DJI PILOT 2",
    title: "Su vuelo, conectado.",
    intro:
      "Comparta telemetría con su Flying Lab mientras sigue volando con DJI Pilot 2.",
    outsideTitle: "Abra esta página en DJI Pilot 2",
    outsideBody:
      "En el controlador compatible, abra Cloud Service → Open Platforms e introduzca la dirección de este sitio. Un navegador normal no puede conectar la aeronave desde esta página.",
    step: "CONFIGURACIÓN DEL CONTROLADOR",
    connectTitle: "Conecte con su laboratorio",
    connectBody:
      "Use el código privado que el coordinador le entregó para este controlador.",
    codeLabel: "Código de conexión",
    codeHelp:
      "Es un código de configuración del controlador, no su contraseña de Passport. Manténgalo privado.",
    connect: "Conectar telemetría →",
    connectionLabel: "ESTADO DE LA CONEXIÓN",
    controller: "Conexión del controlador",
    aircraft: "Telemetría de la aeronave",
    blender: "Flight Blender",
    received: "Última muestra de la aeronave",
    accepted: "Última aceptación de la API",
    pending: "Pendientes de envío",
    disconnect: "Desconectar este controlador",
    note: "Solo conexión de telemetría. La identidad del piloto, los permisos y las revisiones siguen el procedimiento del laboratorio. No se solicita acceso al control de vuelo.",
    help: "¿Necesita ayuda? Contacte con el coordinador que le dio este enlace.",
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
      "Este código es de otro controlador. Pida el correcto al coordinador.",
    dji_configuration_pending:
      "La conexión DJI del laboratorio aún no está configurada. Contacte con el coordinador.",
    try_later: "Demasiados intentos. Espere un minuto y vuelva a intentarlo.",
    invalid_fields: "Compruebe el código e inténtelo de nuevo.",
    generic:
      "No se pudo conectar. Compruebe internet y consulte al coordinador si persiste.",
    licenseError:
      "DJI no pudo verificar la licencia. Pida al coordinador que revise la configuración DJI.",
    bridgeError:
      "Pilot 2 no pudo cargar la conexión. Pida revisar el controlador compatible y la versión de Pilot.",
    sampleHelp:
      "Esperando una posición reciente de una aeronave aprobada. Revise su configuración normal en tierra con el coordinador.",
    activeHelp:
      "Llegan datos recientes. La aceptación confirma recepción por la API de Blender; el laboratorio debe verificar también el registro en su panel.",
    backendHelp:
      "La conexión con Blender necesita revisión. El coordinador puede comprobar credenciales y estado del servidor.",
    nativeHelp:
      "Pilot 2 sigue conectando con el servicio. Compruebe internet y la configuración del laboratorio.",
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
}
function native(method, ...args) {
  if (!bridge || typeof bridge[method] !== "function")
    throw new Error("bridgeError");
  let value = bridge[method](...args);
  if (typeof value === "string") {
    try {
      value = JSON.parse(value);
    } catch {
      throw new Error("bridgeError");
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
async function api(path, body) {
  const response = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
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
  el("device-name").textContent = config.device_name;
  el("workspace-name").textContent = config.workspace_name;
  el("connect-card").hidden = true;
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
translate();
el("browser-notice").hidden = Boolean(bridge);
el("connect").disabled = !bridge;
resume();
