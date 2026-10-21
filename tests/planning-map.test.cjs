const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('src/dji_cloud_adaptor/web/planning-map.js', 'utf8');

function fixture({tiles = true, library = true} = {}) {
  const mapEvents = {}, tileEvents = {}, markers = [], groups = [], requests = [], changes = [], saved = [];
  const map = {fits: 0, removed: false, setView() {}, invalidateSize() {},
    on(event, fn) { mapEvents[event] = fn; return this; },
    fitBounds() { this.fits++; }, distance(a, b) { return b.metres; }, remove() {this.removed = true;}};
  const layer = (extra = {}) => ({...extra, addTo(target) {if (target.items) target.items.push(this); return this;}});
  const L = {
    map: () => map,
    featureGroup() {const group = layer({items: [],clearLayers() {this.items=[];},
      getBounds() {return {isValid: () => this.items.length > 0};},eachLayer(fn) {this.items.forEach(fn);}});
      groups.push(group); return group;},
    control: {scale: () => layer(),attribution: () => layer({addAttribution(value) {requests.push({attribution:value}); return this;}})},
    tileLayer(url, options) { requests.push({url,options}); return layer({on(event,fn) {tileEvents[event]=fn; return this;}}); },
    circle(centre, options) {return layer({centre,radius:options.radius,setRadius(value) {this.radius=value;}});},
    marker(centre, options) {const events={};const value=layer({centre,options,events,
      on(event,fn) {events[event]=fn;return this;},getLatLng() {return {metres:230};}});markers.push(value);return value;},
    divIcon: options => options,
    geoJSON(geometry) {saved.push(geometry);return layer();},
  };
  const context = {window: library ? {L} : {}};
  vm.createContext(context); vm.runInContext(source, context);
  const message={textContent:''}, element={querySelectorAll: () => []};
  const view=context.window.DeclarationMap({element,message,label:key=>key,onRadius:value=>changes.push(value),maximum:()=>500});
  const config={tile_url:tiles?'https://tiles.example.org/{z}/{x}/{y}.png':'',
    attribution:'Maps <unsafe>',attribution_url:'https://example.org/maps',max_zoom:19};
  const position={serial:'A',lat:51,lon:1,observed_at:100,elevation:0};
  return {view,message,map,mapEvents,tileEvents,markers,groups,requests,changes,saved,config,position};
}

test('live area resizes on tap and drag within limits without resetting the map on polling', () => {
  const f=fixture();
  f.view.live(f.position,100,102,f.config);
  assert.equal(f.map.fits,1);
  f.mapEvents.click({latlng:{metres:900}});
  assert.equal(f.changes.at(-1),500);
  const handle=f.markers.at(-1);
  handle.events.dragstart(); handle.events.drag();
  assert.equal(f.changes.at(-1),230);
  const count=f.markers.length;
  f.view.live(f.position,230,103,f.config);
  assert.equal(f.markers.length,count); // Polling must not destroy a handle under the pilot's finger.
  handle.events.dragend();
  assert.equal(f.map.fits,1);
});

test('review uses the exact saved GeoJSON and prevents resizing', () => {
  const f=fixture();
  f.view.live(f.position,100,102,f.config);
  const geometry={type:'FeatureCollection',features:[{type:'Feature',properties:{takeoff_reference:{lat:51,lon:1}},
    geometry:{type:'Polygon',coordinates:[[[1,51],[1.01,51],[1,51.01],[1,51]]]}}]};
  f.view.saved(geometry,f.config);
  f.mapEvents.click({latlng:{metres:400}});
  assert.equal(f.changes.length,0);
  assert.equal(f.saved[0],geometry);
  assert.equal(f.message.textContent,'savedBoundary');
});

test('stale or airborne positions clear the proposed footprint and block map resizing', () => {
  const f=fixture();
  f.view.live(f.position,100,102,f.config);
  f.view.live({...f.position,elevation:30},100,103,f.config);
  assert.equal(f.groups[0].items.length,0);
  assert.equal(f.message.textContent,'mapWaiting');
  f.mapEvents.click({latlng:{metres:200}});
  assert.equal(f.changes.length,0);
  f.view.live(f.position,100,111,f.config);
  assert.equal(f.groups[0].items.length,0);
});

test('partial tile failures stay visible until the failed tile recovers or leaves the view', () => {
  const f=fixture();
  f.view.live(f.position,100,102,f.config);
  f.tileEvents.tileerror({coords:{z:16,x:1,y:2}});
  f.tileEvents.tileload({coords:{z:16,x:2,y:2}});
  assert.equal(f.message.textContent,'tilesUnavailable');
  assert(f.groups[0].items.length > 0);
  f.tileEvents.tileload({coords:{z:16,x:1,y:2}});
  assert.equal(f.message.textContent,'mapHint');
  const request=f.requests.find(row=>row.url);
  assert.equal(request.options.referrerPolicy,'origin');
  assert.equal(request.options.keepBuffer,0);
  assert.match(f.requests.find(row=>row.attribution).attribution,/&lt;unsafe&gt;/);
});

test('outline-only mode makes no tile requests; missing library retains numeric planning', () => {
  const f=fixture({tiles:false});
  f.view.live(f.position,100,102,f.config);
  assert.equal(f.requests.length,0);
  assert.equal(f.message.textContent,'outlineOnly');
  const missing=fixture({library:false});
  missing.view.live(missing.position,100,102,missing.config);
  assert.equal(missing.message.textContent,'mapUnavailable');
});

test('disconnect destroys the map and clears its location', () => {
  const f=fixture();
  f.view.live(f.position,100,102,f.config);
  f.view.clear();
  assert.equal(f.map.removed,true);
  assert.equal(f.message.textContent,'');
});
