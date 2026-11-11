"use strict";
// The connection code grants device access. Roster selection does not authenticate a person.
window.PilotDeclarations = function ({ api, language, aircraftSerial }) {
  const $ = (id) => document.getElementById(id);
  const words = {
    en: {
      plannerLabel: "VLOS FLIGHT PLAN", stepPlan: "Plan", stepReview: "Review", stepDeclare: "Declare",
      operatingArea: "Operating area", fitArea: "Fit area", areaKey: "Flight area", takeoffMarker: "Take-off point",
      areaAndHeight: "Area and height", flightWindow: "Flight window", crewAndAircraft: "Pilot and aircraft",
      startSoon: "In 2 minutes", shortRadius: "Radius", shortHeight: "Height", shortDuration: "Duration",
      technicalDetails: "Declaration details", decrease: "Decrease", increase: "Increase",
      mapScope: "Street map only. Airspace restrictions are not shown.",
      area_not_supported: "This planner does not support this location. Use your organisation’s planning procedure.",
      mapHint: "Tap the map or drag the ↔ handle to resize. The circle stays centred on take-off.",
      mapWaiting: "Waiting for a recent ground position from the selected aircraft.",
      mapUnavailable: "Map unavailable. You can enter the radius and review the coordinates below.",
      tilesUnavailable: "Basemap unavailable. The flight area and take-off marker remain visible.",
      outlineOnly: "Area outline only. No basemap is configured.", savedBoundary: "Saved declaration boundary.",
      radiusHandle: "Drag to change the area radius", proposedArea: "Proposed area", savedArea: "Saved area", previousFlight: "Previous declaration", zoomIn: "Zoom in", zoomOut: "Zoom out",
      title: "Flight declaration", intro: "Set the flight area, height and time. Review the plan before submitting.",
      pilot: "Pilot", aircraft: "Aircraft", radius: "Area radius (m)", height: "Maximum height above take-off (m)",
      start: "Start (controller local time)", duration: "Duration (minutes)",
      ground: "Aircraft on the ground. The plan covers my flight and operating checks are complete.",
      prepare: "Review plan", submit: "Submit declaration", refresh: "Check status", activate: "Activate declaration",
      finish: "End declaration after landing", cancel: "Cancel declaration", discard: "Edit plan",
      limit: "Organisation limits", review: "Review before submission", centre: "Take-off point", volume: "Declared altitude range (WGS84 ellipsoid, m)",
      window: "Flight window", identifier: "Declaration ID", pilotInfo: "Pilot selection records responsibility. It is not a personal sign-in.",
      disclaimer: "A declaration does not grant flight permission or control the aircraft. Activate it only when you are ready to fly. End it after landing.",
      waiting: "Checking declaration…", unavailable: "Declaration status unavailable. Check internet, then use Check status. Do not submit another plan to recover a lost response.",
      uncertain: "Submission is unconfirmed. Check status to find the saved declaration. If it remains unconfirmed, contact your administrator; do not create a replacement.",
      prepared: "Draft — not submitted", not_submitted: "Not submitted to network", accepted: "Accepted", activated: "Activated", nonconforming: "Nonconforming", contingent: "Contingent", ended: "Ended", withdrawn: "Withdrawn", cancelled: "Cancelled", rejected: "Rejected", discarded: "Draft discarded", unknown: "Unknown",
      approval: "Approval recorded by Blender", yes: "Yes", no: "No", finishing: "Ending: telemetry is draining. Use End declaration again when waiting samples reach zero.",
      samples: "Declaration telemetry: API accepted / waiting / rejected or expired", last: "Last declaration API acceptance",
      ground_sample_required: "A position at ground level is required. Keep the aircraft powered on at the take-off point. Check telemetry, then review again.",
      operation_already_open: "This aircraft already has an open plan. Check status to recover it.",
      plan_start: "Choose a start at least 15 seconds ahead and within the next 24 hours. Choose Edit plan to update an expired draft.",
      plan_limits: "The plan exceeds your organisation’s limits. Check the radius, height and duration.",
      activation_not_allowed: "Activation needs an accepted, approved declaration within its flight window. Check status or contact your coordinator.",
      plan_conflict: "The saved plan differs from this request. Check status before continuing.",
      invalid_fields: "Complete all plan fields with valid values and confirm the operating checks.",
    },
    es: {
      plannerLabel: "PLAN DE VUELO VLOS", stepPlan: "Planificar", stepReview: "Revisar", stepDeclare: "Declarar",
      operatingArea: "Área de operación", fitArea: "Ver área", areaKey: "Área de vuelo", takeoffMarker: "Punto de despegue",
      areaAndHeight: "Área y altura", flightWindow: "Horario de vuelo", crewAndAircraft: "Piloto y aeronave",
      startSoon: "En 2 minutos", shortRadius: "Radio", shortHeight: "Altura", shortDuration: "Duración",
      technicalDetails: "Detalles de declaración", decrease: "Reducir", increase: "Aumentar",
      mapScope: "Solo mapa de calles. No muestra restricciones del espacio aéreo.",
      area_not_supported: "El planificador no admite esta ubicación. Use el procedimiento de su organización.",
      mapHint: "Toque el mapa o arrastre ↔ para ajustar el radio. El centro permanece en el despegue.",
      mapWaiting: "Esperando una posición reciente en tierra de la aeronave seleccionada.",
      mapUnavailable: "Mapa no disponible. Puede introducir el radio y revisar las coordenadas abajo.",
      tilesUnavailable: "Mapa base no disponible. El área de vuelo y el punto de despegue siguen visibles.",
      outlineOnly: "Solo contorno. No hay mapa base configurado.", savedBoundary: "Límite guardado de la declaración.",
      radiusHandle: "Arrastre para cambiar el radio", proposedArea: "Área propuesta", savedArea: "Área guardada", previousFlight: "Declaración anterior", zoomIn: "Acercar", zoomOut: "Alejar",
      title: "Declaración de vuelo", intro: "Defina el área, la altura y el horario. Revise el plan antes de enviar.",
      pilot: "Piloto", aircraft: "Aeronave", radius: "Radio del área (m)", height: "Altura máxima sobre el despegue (m)",
      start: "Inicio (hora local del controlador)", duration: "Duración (minutos)",
      ground: "Aeronave en tierra. El plan cubre mi vuelo y completé las comprobaciones operativas.",
      prepare: "Revisar plan", submit: "Enviar declaración", refresh: "Consultar estado", activate: "Activar declaración",
      finish: "Finalizar declaración tras aterrizar", cancel: "Cancelar declaración", discard: "Editar plan",
      limit: "Límites de la organización", review: "Revise antes de enviar", centre: "Punto de despegue", volume: "Rango de altitud declarado (elipsoide WGS84, m)",
      window: "Horario del vuelo", identifier: "ID de declaración", pilotInfo: "La selección del piloto registra la responsabilidad. No es un inicio de sesión personal.",
      disclaimer: "Una declaración no otorga permiso de vuelo ni controla la aeronave. Actívela solo cuando esté listo para volar. Finalícela después de aterrizar.",
      waiting: "Consultando declaración…", unavailable: "Estado de declaración no disponible. Revise internet y pulse Consultar estado. No envíe otro plan para recuperar una respuesta perdida.",
      uncertain: "Envío sin confirmar. Consulte el estado para encontrar la declaración guardada. Si sigue sin confirmar, contacte al administrador; no cree otra.",
      prepared: "Borrador — sin enviar", not_submitted: "Sin enviar a la red", accepted: "Aceptada", activated: "Activada", nonconforming: "No conforme", contingent: "Contingencia", ended: "Finalizada", withdrawn: "Retirada", cancelled: "Cancelada", rejected: "Rechazada", discarded: "Borrador descartado", unknown: "Desconocido",
      approval: "Aprobación registrada por Blender", yes: "Sí", no: "No", finishing: "Finalizando: se está enviando la telemetría pendiente. Pulse Finalizar declaración otra vez cuando no queden muestras en espera.",
      samples: "Telemetría de la declaración: API aceptó / en espera / rechazada o vencida", last: "Última aceptación de la API para la declaración",
      ground_sample_required: "Se requiere una posición a nivel del suelo. Mantenga la aeronave encendida en el punto de despegue. Revise la telemetría y vuelva a revisar el plan.",
      operation_already_open: "Esta aeronave ya tiene un plan abierto. Consulte el estado para recuperarlo.",
      plan_start: "Elija un inicio al menos 15 segundos después y dentro de las próximas 24 horas. Elija Editar plan para actualizar un borrador vencido.",
      plan_limits: "El plan supera los límites de la organización. Revise radio, altura y duración.",
      activation_not_allowed: "Se necesita una declaración aceptada y aprobada dentro de su horario para activar. Consulte el estado o contacte al coordinador.",
      plan_conflict: "El plan guardado difiere de esta solicitud. Consulte el estado antes de continuar.",
      invalid_fields: "Complete todos los campos con valores válidos y confirme las comprobaciones operativas.",
    },
  };
  const tr = (key) => words[language()][key] || words[language()].unavailable;
  let enabled = false, busy = false, current = null, requestId = "", pendingPlan = null, generation = 0;
  let options = null, optionsReceivedAt = 0;
  const selectChoices = new Map();
  const planningMap = window.DeclarationMap({
    element: $("declaration-map"), message: $("declaration-map-message"), label: tr,
    maximum: () => options ? options.limits.radius_m : 10000,
    onRadius: (value) => { $("declaration-radius").value = String(value); },
  });
  function step(active) {
    for (const name of ["plan", "review", "declare"]) {
      $("planner-step-" + name).setAttribute("aria-current", name === active ? "step" : "false");
    }
  }
  function liveMap() {
    if (!options) return;
    const selected = $("declaration-aircraft").value;
    const position = (options.positions || []).find((point) => point.serial === selected);
    $("declaration-map-caption").textContent = tr("proposedArea");
    planningMap.live(position, Number($("declaration-radius").value), options.server_time, options.map);
  }
  function presets() {
    for (const minutes of [15, 30, 60]) {
      const button = $("declaration-duration-" + minutes);
      button.disabled = Boolean(options && minutes > options.limits.duration_minutes);
      button.setAttribute("aria-pressed", Number($("declaration-duration").value) === minutes ? "true" : "false");
    }
  }
  function startSoon() {
    if (!options) return;
    const now = options.server_time + (Date.now() - optionsReceivedAt) / 1000;
    const start = new Date((now + 120) * 1000);
    start.setMinutes(start.getMinutes() - start.getTimezoneOffset());
    $("declaration-start").value = start.toISOString().slice(0, 16);
  }
  function translate() {
    document.querySelectorAll("[data-declaration-text]").forEach((node) => {
      node.textContent = tr(node.dataset.declarationText);
    });
    for (const field of ["radius", "height", "duration"]) {
      $("declaration-" + field + "-less").setAttribute("aria-label", `${tr("decrease")} ${tr(field)}`);
      $("declaration-" + field + "-more").setAttribute("aria-label", `${tr("increase")} ${tr(field)}`);
    }
    $("declaration-map").setAttribute("aria-label", tr("operatingArea"));
    $("planner-steps").setAttribute("aria-label", `${tr("stepPlan")}, ${tr("stepReview")}, ${tr("stepDeclare")}`);
    $("planner-duration-presets").setAttribute("aria-label", tr("duration"));
    if (current) render(current);
    planningMap.translate();
  }
  function clear() {
    generation++;
    planningMap.clear();
    selectChoices.clear();
    document.documentElement.classList.toggle("planning", false);
    enabled = false; current = null; options = null; requestId = ""; pendingPlan = null;
    $("declaration-card").hidden = true;
    $("declaration-pilot").textContent = "";
    $("declaration-aircraft").textContent = "";
    $("declaration-summary").textContent = "";
    $("declaration-status").textContent = "";
    $("declaration-message").textContent = "";
    for (const id of ["radius", "height", "duration", "start"]) $("declaration-" + id).value = "";
    $("declaration-ground").checked = false;
  }
  function actionButtons(available) {
    for (const action of ["submit", "activate", "finish", "cancel", "discard"]) {
      $("declaration-" + action).hidden = !available.includes(action);
      $("declaration-" + action).disabled = busy;
    }
    $("declaration-prepare").disabled = busy || Boolean(pendingPlan);
    $("declaration-refresh").disabled = busy;
  }
  function render(op) {
    current = op;
    const closed = ["closed", "discarded"].includes(op.stage);
    $("declaration-form").hidden = !closed;
    $("declaration-review").hidden = closed;
    step(op.stage === "prepared" ? "review" : closed ? "plan" : "declare");
    if (!closed) {
      planningMap.saved(op.geometry, options ? options.map : {});
      $("declaration-map-caption").textContent = tr("savedArea");
    } else liveMap();
    $("review-radius").textContent = `${op.plan.radius_m} m`;
    $("review-height").textContent = `${op.plan.height_m} m`;
    $("review-duration").textContent = `${op.plan.duration_minutes} min`;
    $("declaration-review-crew").textContent = `${op.pilot_name} · ${op.aircraft_sn}`;
    $("declaration-review-window").textContent = `${new Date(op.start).toLocaleString(language())} – ${new Date(op.end).toLocaleString(language())}`;
    const props = op.geometry.features[0].properties;
    const reference = props.takeoff_reference;
    const localDate = (value) => new Date(value).toLocaleString(language() === "es" ? "es" : "en");
    $("declaration-summary").textContent = [
      `${tr("pilot")}: ${op.pilot_name}`, `${tr("aircraft")}: ${op.aircraft_sn}`,
      `${tr("centre")}: ${reference.lat.toFixed(6)}, ${reference.lon.toFixed(6)}`,
      `${tr("radius")}: ${op.plan.radius_m}`, `${tr("height")}: ${op.plan.height_m}`,
      `${tr("volume")}: ${props.min_altitude.meters.toFixed(1)} – ${props.max_altitude.meters.toFixed(1)}`,
      `${tr("window")}: ${localDate(op.start)} – ${localDate(op.end)}`,
      `${tr("identifier")}: ${op.declaration_id || "—"}`,
    ].join("\n");
    const fresh = op.checked_at && options && options.server_time - op.checked_at < 30 && !op.error;
    const state = ["prepared", "discarded"].includes(op.stage) ? op.stage
      : !fresh && !closed ? "unknown" : op.state;
    $("declaration-status").textContent = `${tr(state)} · ${tr("approval")}: ${tr(op.approved ? "yes" : "no")}`;
    $("declaration-status").className = "notice";
    const counts = op.telemetry_counts;
    $("declaration-telemetry").textContent = `${tr("samples")}: ${counts.accepted || 0} / ${counts.pending || 0} / ${(counts.rejected || 0) + (counts.expired || 0)}. ${tr("last")}: ${op.last_api_acceptance ? localDate(op.last_api_acceptance * 1000) : "—"}`;
    let actions = ["refresh"];
    if (op.stage === "prepared") actions = ["submit", "discard"];
    if (op.stage === "submitted" && fresh) {
      if (op.state === "accepted" && op.approved) actions.push("activate");
      if (["not_submitted", "accepted"].includes(op.state)) actions.push("cancel");
      if (["activated", "nonconforming", "contingent"].includes(op.state)) actions.push("finish");
    }
    if (op.stage === "finishing" && fresh) actions.push("finish");
    actionButtons(actions);
    $("declaration-message").textContent = op.stage === "uncertain" ? tr("uncertain")
      : op.stage === "finishing" ? tr("finishing") : op.error ? tr("unavailable")
      : op.stage === "closed" ? `${tr("previousFlight")}: ${tr(op.state)}` : "";
  }
  function fillSelect(id, rows, key) {
    const signature = JSON.stringify(rows.map((row) => [row[key], row.name]));
    if (selectChoices.get(id) === signature) return;
    selectChoices.set(id, signature);
    const previous = $(id).value;
    $(id).textContent = "";
    for (const row of rows) {
      const option = document.createElement("option");
      option.value = row[key]; option.textContent = row.name;
      $(id).appendChild(option);
    }
    if (rows.some((row) => row[key] === previous)) $(id).value = previous;
  }
  async function poll() {
    if (!enabled || busy) return;
    const version = generation;
    try {
      const result = await api("/api/pilot/declarations");
      if (!enabled || version !== generation) return;
      options = result; optionsReceivedAt = Date.now();
      $("declaration-card").hidden = false;
      if (!$("declaration-start").value) startSoon();
      if (!requestId) requestId = result.request_id;
      fillSelect("declaration-pilot", result.pilots, "id");
      fillSelect("declaration-aircraft", result.aircraft, "serial");
      const serial = aircraftSerial();
      if (!current && result.aircraft.some((row) => row.serial === serial)) $("declaration-aircraft").value = serial;
      for (const field of ["radius", "height", "duration"]) {
        $("declaration-" + field).max = result.limits[field === "duration" ? "duration_minutes" : field + "_m"];
      }
      for (const [field, initial] of [["radius", 100], ["height", 50], ["duration", 30]]) {
        const input = $("declaration-" + field);
        if (!input.value) input.value = String(Math.min(initial, Number(input.max)));
      }
      $("declaration-height").min = Math.min(1, result.limits.height_m);
      presets();
      $("declaration-limits").textContent = `${tr("limit")}: ${tr("shortRadius")} ≤ ${result.limits.radius_m} m · ${tr("shortHeight")} ≤ ${result.limits.height_m} m.`;
      const recovered = result.operations.find((op) => !["closed", "discarded"].includes(op.stage))
        || result.operations.find((op) => op.id === (current && current.id));
      if (recovered) {
        current = recovered; pendingPlan = null;
        render(current);
      } else if (!current) {
        $("declaration-form").hidden = false;
        $("declaration-review").hidden = true;
        actionButtons([]);
        step("plan"); liveMap();
      }
      $("declaration-card").hidden = false;
    } catch {
      if (version !== generation || !enabled) return;
      $("declaration-message").textContent = tr("unavailable");
      if (!current || ["closed", "discarded"].includes(current.stage)) {
        planningMap.live(null, Number($("declaration-radius").value), 0, options ? options.map : {});
      }
      $("declaration-status").textContent = tr("unknown");
      actionButtons([]);
    }
  }
  async function connect(config) {
    clear();
    enabled = config.declarations_enabled === true;
    document.documentElement.classList.toggle("planning", enabled);
    if (enabled) { translate(); await poll(); }
  }
  $("declaration-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!enabled || busy || pendingPlan) return;
    const version = generation;
    try {
      pendingPlan = {request_id: requestId, pilot_id: $("declaration-pilot").value,
        aircraft_sn: $("declaration-aircraft").value, radius_m: Number($("declaration-radius").value),
        height_m: Number($("declaration-height").value), duration_minutes: Number($("declaration-duration").value),
        start: new Date($("declaration-start").value).toISOString(), on_ground: $("declaration-ground").checked};
      if (current && ["closed", "discarded"].includes(current.stage)) current = null;
      busy = true; actionButtons([]);
      const op = await api("/api/pilot/declarations", pendingPlan);
      if (version !== generation || !enabled) return;
      current = op; pendingPlan = null;
    } catch (error) {
      if (version !== generation || !enabled) return;
      // Keep an ambiguous request frozen; Check status recovers the saved draft.
      if (error.status && error.status < 500) pendingPlan = null;
      $("declaration-message").textContent = tr(error.message);
    } finally {
      busy = false;
      if (version === generation && enabled) {
        if (current) render(current); else actionButtons([]);
      }
    }
  });
  for (const action of ["submit", "refresh", "activate", "finish", "cancel", "discard"]) {
    $("declaration-" + action).addEventListener("click", async () => {
      if (!enabled || busy) return;
      const version = generation;
      busy = true; actionButtons([]);
      let failure = "";
      const editing = action === "discard" && current && current.stage === "prepared" ? current.plan : null;
      try {
        if (pendingPlan) {
          // Same frozen request ID and body: safe even if the first response was lost.
          current = await api("/api/pilot/declarations", pendingPlan);
          pendingPlan = null;
        } else if (current && !(action === "refresh" && ["discarded", "closed"].includes(current.stage))) {
          const op = await api(`/api/pilot/declarations/${current.id}`, {action});
          if (version !== generation || !enabled) return;
          current = op;
        }
        if (current && ["closed", "discarded"].includes(current.stage)) {
          requestId = "";
          $("declaration-ground").checked = false;
          $("declaration-start").value = "";
          if (editing) {
            $("declaration-radius").value = String(editing.radius_m);
            $("declaration-height").value = String(editing.height_m);
            $("declaration-duration").value = String(editing.duration_minutes);
            $("declaration-pilot").value = editing.pilot_id;
            $("declaration-aircraft").value = editing.aircraft_sn;
            const start = new Date(editing.start);
            start.setMinutes(start.getMinutes() - start.getTimezoneOffset());
            $("declaration-start").value = start.toISOString().slice(0, 16);
            if (Date.parse(editing.start) / 1000 < options.server_time + 15) startSoon();
          }
        }
      } catch (error) { failure = tr(error.message); }
      finally {
        busy = false;
        if (version === generation && enabled) {
          if (current) render(current);
          await poll();
          if (failure) $("declaration-message").textContent = failure;
        }
      }
    });
  }
  for (const [field, increment] of [["radius", 50], ["height", 10], ["duration", 5]]) {
    const input = $("declaration-" + field);
    for (const [suffix, sign] of [["less", -1], ["more", 1]]) {
      $("declaration-" + field + "-" + suffix).addEventListener("click", () => {
        const minimum = Number(input.min) || 1, maximum = Number(input.max) || 10000;
        input.value = String(Math.max(minimum, Math.min(maximum, (Number(input.value) || minimum) + sign * increment)));
        if (field === "radius") planningMap.setRadius(Number(input.value));
        presets();
      });
    }
    input.addEventListener("input", () => {
      if (field === "radius") planningMap.setRadius(Number(input.value));
      presets();
    });
  }
  for (const minutes of [15, 30, 60]) {
    $("declaration-duration-" + minutes).addEventListener("click", () => {
      if (!options || minutes > options.limits.duration_minutes) return;
      $("declaration-duration").value = String(minutes); presets();
    });
  }
  $("declaration-start-soon").addEventListener("click", startSoon);
  $("declaration-fit").addEventListener("click", () => planningMap.fit());
  $("declaration-aircraft").addEventListener("change", liveMap);
  return { connect, poll, clear, translate };
};
