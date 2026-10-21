"use strict";
// Bundled Leaflet; only the configured raster tile origin receives viewport requests.
window.DeclarationMap = function ({ element, message, label, onRadius, maximum }) {
  let map = null, layers = null, tiles = null, handle = null, position = null, radius = 100;
  let locked = false, fitted = false, savedKey = "", tileFailed = false, hasTiles = false, dragging = false;
  const failedTiles = new Set();
  const escape = (value) => String(value).replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]);
  function notify() {
    message.textContent = label(!window.L ? "mapUnavailable" : tileFailed ? "tilesUnavailable"
      : locked ? "savedBoundary" : !position ? "mapWaiting" : !hasTiles ? "outlineOnly" : "mapHint");
  }
  function init(config) {
    if (!window.L) { notify(); return false; }
    if (map) return true;
    const L = window.L;
    map = L.map(element, {attributionControl: false, scrollWheelZoom: false, maxZoom: config.max_zoom || 19});
    map.setView([0, 0], 2);
    layers = L.featureGroup().addTo(map);
    L.control.scale({imperial: false}).addTo(map);
    if (config.tile_url) {
      hasTiles = true;
      tiles = L.tileLayer(config.tile_url, {maxZoom: config.max_zoom || 19, referrerPolicy: "origin",
        updateWhenIdle: true, keepBuffer: 0}).addTo(map);
      const tileKey = (event) => [event.coords.z, event.coords.x, event.coords.y].join("/");
      tiles.on("tileerror", (event) => { failedTiles.add(tileKey(event)); tileFailed = true; notify(); });
      const recovered = (event) => { failedTiles.delete(tileKey(event)); tileFailed = failedTiles.size > 0; notify(); };
      tiles.on("tileload", recovered);
      tiles.on("tileunload", recovered);
      L.control.attribution({prefix: false}).addAttribution(
        `<a href="${escape(config.attribution_url)}" target="_blank" rel="noopener noreferrer">${escape(config.attribution)}</a>`
      ).addTo(map);
    }
    map.on("click", (event) => {
      if (!locked && position) resize(map.distance([position.lat, position.lon], event.latlng));
    });
    translate();
    return true;
  }
  function resize(value) {
    radius = Math.max(10, Math.min(maximum(), Math.round(value)));
    onRadius(radius);
    draw();
  }
  function marker(point, className, html, options = {}) {
    return window.L.marker(point, {icon: window.L.divIcon({className, html, iconSize: [30,30], iconAnchor: [15,15]}), ...options});
  }
  function draw() {
    if (!map || !position || locked || dragging) return;
    const L = window.L, centre = [position.lat, position.lon];
    layers.clearLayers();
    L.circle(centre, {radius, color: "#116b69", weight: 2, fillColor: "#25a39a", fillOpacity: 0.15}).addTo(layers);
    marker(centre, "takeoff-marker", "H", {title: label("takeoffMarker"), keyboard: true}).addTo(layers);
    const longitude = position.lon + radius / (111195 * Math.cos(position.lat * Math.PI / 180));
    handle = marker([position.lat, longitude], "radius-marker", "↔", {draggable: true, title: label("radiusHandle")}).addTo(layers);
    handle.on("dragstart", () => { dragging = true; });
    handle.on("drag", () => {
      radius = Math.max(10, Math.min(maximum(), Math.round(map.distance(centre, handle.getLatLng()))));
      onRadius(radius);
      // Update the circle without replacing the handle during an active drag.
      layers.eachLayer((layer) => { if (typeof layer.setRadius === "function") layer.setRadius(radius); });
    });
    handle.on("dragend", () => { dragging = false; draw(); });
    if (!fitted) fit();
    notify();
  }
  function fit() {
    if (!map || !layers) return;
    map.invalidateSize();
    const bounds = layers.getBounds();
    if (bounds.isValid()) { map.fitBounds(bounds, {padding: [44,44], maxZoom: 18, animate: false}); fitted = true; }
  }
  function live(value, nextRadius, serverTime, config = {}) {
    locked = false; savedKey = "";
    radius = Number.isFinite(nextRadius) && nextRadius >= 10 ? nextRadius : 100;
    const ground = value && serverTime - value.observed_at >= 0 && serverTime - value.observed_at <= 10
      && value.elevation !== null && value.elevation !== undefined && Math.abs(value.elevation) <= 2;
    if (!ground) {
      position = null;
      if (layers) layers.clearLayers();
      notify();
      return;
    }
    if (position && position.serial !== value.serial) fitted = false;
    position = value;
    if (init(config)) draw();
    notify();
  }
  function saved(geometry, config = {}) {
    const key = JSON.stringify(geometry);
    locked = true;
    if (!init(config)) return;
    if (savedKey === key) { notify(); return; }
    savedKey = key;
    layers.clearLayers();
    const props = geometry.features[0].properties;
    const reference = props.takeoff_reference;
    window.L.geoJSON(geometry, {style: {color: "#116b69", weight: 3, fillColor: "#25a39a", fillOpacity: 0.18}}).addTo(layers);
    marker([reference.lat, reference.lon], "takeoff-marker", "H", {title: label("takeoffMarker")}).addTo(layers);
    fit(); notify();
  }
  function setRadius(value) {
    if (Number.isFinite(value) && value >= 10) { radius = Math.min(maximum(), value); draw(); }
  }
  function clear() {
    if (map) map.remove();
    map = null; layers = null; tiles = null; handle = null; position = null;
    fitted = false; savedKey = ""; tileFailed = false; hasTiles = false; locked = false; dragging = false;
    failedTiles.clear();
    message.textContent = "";
  }
  function translate() {
    notify();
    if (!map) return;
    for (const [selector, key] of [[".leaflet-control-zoom-in", "zoomIn"], [".leaflet-control-zoom-out", "zoomOut"],
        [".takeoff-marker", "takeoffMarker"], [".radius-marker", "radiusHandle"]]) {
      element.querySelectorAll(selector).forEach((node) => {
        node.title = label(key); node.setAttribute("aria-label", label(key));
      });
    }
  }
  return {live, saved, setRadius, fit, clear, translate};
};
