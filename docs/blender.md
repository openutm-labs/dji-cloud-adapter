# Flight Blender integration contract

[Home](../README.md) · [Protocol](protocol.md) · [Acceptance](acceptance.md)

## Default traffic endpoint

`POST /flight_stream/set_air_traffic/{session_id}` with `Authorization: Bearer ...` and an `observations` array. Verify this contract against your deployment’s OpenAPI document at `<BLENDER_BASE_URL>/openapi.json`.

The adapter generates a stable UUID traffic session per configured aircraft. It is not an automatically created or approved operation. With declarations disabled, this is the only telemetry write endpoint. The optional workflow below creates declarations separately; it never overrides approval or calls DSS submission directly.

## Mapping

| DJI field | Blender field | Conversion |
|---|---|---|
| `data.latitude` | `lat_dd` | Degrees, unchanged. |
| `data.longitude` | `lon_dd` | Degrees, unchanged. |
| `data.height` | `altitude_mm` | WGS84 ellipsoid metres × 1000. |
| Envelope `timestamp` | `timestamp` | Original milliseconds, unchanged. |
| Configured aircraft | `icao_address` | Stable 24-character opaque `dji-...` ID; explicitly not an assigned ICAO address. |
| `elevation`, speeds, heading, mode | `metadata` | Optional validated values; elevation is relative to take-off. |
| Adapter metadata | `metadata` | Source, workspace UUID, aircraft alias/model, altitude reference, source event ID, no asserted RID compliance. |
| Envelope `timestamp` | `metadata.source_timestamp_ms` | Original milliseconds retained for correlation when a read endpoint omits sensor time. |

The project's resolved API reference defines `traffic_source=11` as Network Remote-ID and `source_type=0` as direct/true rather than fused data. These are configurable defaults, **not an assertion that DJI Cloud telemetry fulfils an ASTM RID service**. Confirm the desired classification and display handling with the Blender team before deployment.

Configured simulation aircraft override this category using an explicitly allocated code 12–255,
`source=dji_cloud_api_simulation`, `simulation=true`, a UUID run ID and an opaque `sim-dji-...` address.
The normal category validation remains 0–11. Code 255 in local tests is not allocated for hosted services.
The service owner must confirm its semantics and operational-consumer exclusion before any hosted run.
See the [simulation isolation and readback procedure](simulation.md). A traffic session UUID alone
does not provide tenant isolation in the reviewed implementation. These observations remain non-RID.

## Authentication

The adapter sends a bearer token to Blender. Obtain the token endpoint, client authentication method, audience, scopes and client credentials from the administrator of your deployment. The write endpoint requires `flightblender.write`; verify the target service’s configuration.

### Server configuration

The following addresses are examples, not deployed services:

| Setting | Example / requirement |
|---|---|
| Blender base URL | `https://blender.example.org` |
| Token URL | `https://auth.example.org/oauth/token/` |
| Grant / client authentication | `client_credentials` / credentials in the form body; issuer must accept `client_secret_post` |
| Audience | The exact value required by the issuer, if any; for example `blender.example.org` |
| Requested scope | `flightblender.read flightblender.write`; confirm permitted scopes with the service administrator |
| Client ID and secret | Private server configuration only; obtain through the authorised service owner |

Keep TLS certificate verification enabled. Never put the client secret in a command argument, shared shell history, controller setup file or documentation. Validate token acquisition/renewal and protected read access using the check below; these do not establish write acceptance or downstream persistence.

Configure **one** server-side mode in private `runtime/config.json`:

- `blender.bearer_token`: supplied token, useful for supervised integration tests. An expired token must be replaced by the administrator.
- `blender.oauth`: `token_url`, `client_id`, `client_secret`, `scope`, and optional `audience`. Uses the `client_credentials` grant with credentials in the form body; verify that the issuer accepts `client_secret_post`. Tokens are cached within their lifetime and refreshed once after a 401. Missing `expires_in` uses a conservative five-minute cache.

The pilot never sees Blender credentials. Redirects from the token/API endpoints are not followed. Token responses and server error bodies are not written to logs/status.

### Check access without submitting traffic

Administrators can run:

```sh
uv run dji-cloud-adaptor check-blender --config runtime/config.json
# With the configured Docker service running:
docker compose --env-file runtime/compose.env -f compose.yml -f compose.development.yml exec -T app dji-cloud-adaptor check-blender --config /config/config.json
```

For a hosted production stack, use `compose.production.yml` instead of `compose.development.yml`. The command obtains a token (or uses the configured bearer token), sends only a protected health GET, retries once with a fresh OAuth token on 401, and exits nonzero on failure. It prints no credentials or server response bodies. It does not establish write permission, telemetry delivery, worker health or flight approval. `/readyz` checks configured credentials and local workers; it is not a replacement for this access check.

## Response and retry behaviour

- HTTP 201/202: **API accepted**. The adapter records the time and stops retrying that sample.
- Network errors, 401/403, 408/409/425/429 and 5xx: retry with exponential backoff, capped at 30 seconds and the sample's live-delivery age.
- Other 4xx: retain the sample as rejected for diagnosis.
- Expired samples: retain locally as expired; never relabel their timestamp or replay them as live traffic.

Blender enqueues ingestion asynchronously. A successful response does not demonstrate persistence, conformance processing or dashboard visibility. Acceptance requires checking those downstream components. A source event ID supports investigation but does not guarantee server-side duplicate suppression.

## What the Blender team must confirm

1. OAuth client ownership, permitted scopes, token endpoint, audience and renewal; verify protected reads and actual traffic writes during supervised acceptance.
2. Traffic-source classification, height datum/units, source timestamp interpretation and opaque aircraft identifier handling.
3. That asynchronous ingestion workers and the intended downstream display consume this traffic feed correctly.
4. If declarations are enabled, verify the declaration, state and operation-telemetry contracts below, scoped pilot roster, planning limits and downstream operation display. A traffic session UUID is not a declaration or flight approval.
5. Historical data ingestion requirements, if any. This version intentionally does not import old flight logs into a live feed.

## Optional pilot declarations

This feature is **disabled by default**. It adds a VLOS area plan to the hosted page inside Pilot 2. It does not read the Pilot 2 mission route or change aircraft controls. Use your organisation’s planning procedure for BVLOS, terrain-following or flights that need other volumes.

Add `declarations` to private `runtime/config.json`, then restart the adapter. This illustrative block must be replaced with your operator, controller IDs, roster and approved limits:

```json
{
  "declarations": {
    "enabled": true,
    "operator_id": "YOUR_OPERATOR_ID",
    "originating_party": "YOUR_ORGANISATION",
    "pilots": [
      {"id": "pilot-01", "name": "Example Pilot", "device_ids": ["YOUR_DEVICE_ID"]}
    ],
    "max_radius_m": 500,
    "max_height_m": 100,
    "max_duration_minutes": 60,
    "altitude_margin_m": 5,
    "timestamp_accuracy_s": 1
  }
}
```

The numbers are examples, **not operating permissions**. Set limits and altitude margin for your accepted operation. Set `timestamp_accuracy_s` to a verified bound on the source clock error in seconds; reporting frequency is not clock accuracy. Do not enable the feature if that bound is unknown. Pilot IDs are stable internal references. `device_ids` explicitly assigns each pilot to controller IDs; there is no wildcard roster. Enrolled IDs are available from the administrator’s device list.

Blender versions can omit operator identity from declaration list fields. The adapter also saves it in the declaration’s raw GeoJSON properties and sends it in operation telemetry. Verify that retained value during acceptance.

The controller connection code grants device access. Selecting a pilot records a claimed responsibility; it does not authenticate that person. Use a controlled controller handover and roster procedure, or add personal authentication before using this for activities that require verified individual identity. Simulation aircraft cannot create declarations.

### Planning map

The planner follows the Android app’s manual-flight layout: map beside settings on wide screens, map above settings on phones. Tap the map or drag the radius handle to resize the circle around the aircraft’s fresh ground position. Height buttons and duration presets reduce typing. **Review plan** locks the map to the exact saved GeoJSON boundary; **Edit plan** restores the draft values for a new review.

Street tiles default to OpenStreetMap. They are a visual reference, not an airspace or terrain-clearance service. The map shows no airspace restrictions. The area outline remains available when street tiles fail; numeric inputs remain available if the map library cannot load.

Administrators can add this top-level setting to the private configuration:

```json
"planning_map": {
  "tile_url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
  "attribution": "© OpenStreetMap contributors",
  "attribution_url": "https://www.openstreetmap.org/copyright",
  "max_zoom": 19
}
```

Choose a provider approved for your deployment. Tile requests reveal the viewed area and page origin to that provider. Browser-visible tile URLs must contain only public client tokens, never private service credentials. An empty `tile_url` disables external tiles and leaves the outline. Scripts and styles are bundled locally using [Leaflet 1.9.4](https://leafletjs.com/reference.html), with its licence and npm integrity record under `web/vendor/leaflet`.

For public OSM tiles, follow the [tile policy](https://operations.osmfoundation.org/policies/tiles/). The map displays attribution, requests viewport tiles only, preserves browser caching and sends an origin-only image referrer. No offline or bulk tile download is provided. The content policy allows images only from the configured tile origin in addition to local assets; API calls remain on the adapter’s origin.

### Plan and lifecycle

1. On the ground at take-off, connect telemetry and select the assigned pilot and aircraft.
2. Enter the area radius, maximum height above take-off, start time and duration. Confirm that the volume covers the intended flight and that operating checks are complete.
3. Resize the circle on the map, with the radius buttons or by entering a value. Select **Review plan**. The adapter requires a source position no older than 10 seconds with take-off-relative elevation within 2 m. Review the saved boundary, altitude range and time window. Exact coordinates and WGS84 limits are under **Declaration details**.
4. Select **Submit declaration**. Wait for Blender’s recorded state and approval. The adapter does not request or grant approval itself.
5. Within the accepted, approved window, select **Activate declaration** when ready to fly. This changes the declaration state only.
6. After landing, select **End declaration after landing**. New samples stop binding to that declaration. If samples are waiting, let the queue drain and select End again. Rejected or expired samples remain visible as gaps.

The area is a 32-sided polygon that encloses the entered radius with 1 m of geometric padding around the ground position. DJI defines [height and elevation](https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/pilot-to-cloud/mqtt/aircraft/properties.html) relative to the ellipsoid and take-off respectively. The take-off WGS84 altitude is `height − elevation`; the declared range is take-off altitude minus the configured margin through take-off altitude plus planned height plus margin. Height above take-off is not height above varying terrain. Review the resulting volume using your organisation’s planning procedure.

| Saved or Blender state | Available action |
|---|---|
| Draft | Submit once or choose **Edit plan**. Editing replaces the draft with a new review; an expired draft needs a new start time. |
| Not submitted to network (0) | Check status or withdraw. |
| Accepted (1), approved | Activate within its time window, or cancel before activation. |
| Activated (2), nonconforming (3), contingent (4) | End after landing; investigate any abnormal state under the operating procedure. |
| Ended (5), withdrawn (6), cancelled (7), rejected (8) | Record the result; a new flight requires a new plan. |
| Submission unconfirmed | Check status to reconcile the saved reference. No second creation POST is sent. |

### Blender contract and recovery

| Request | Purpose |
|---|---|
| `POST /flight_declaration_ops/set_flight_declaration` | Create once. Includes aircraft, operator, pilot, VLOS type, time window, geometry and a unique client reference. No approval or state override is sent. |
| `GET /flight_declaration_ops/flight_declaration/{id}` | Verify saved geometry, submitting pilot, organisation, times, state and approval. |
| `GET /flight_declaration_ops/flight_declaration` | Reconcile an uncertain submission using date filters and numbered pages. Requires `count`, `results` and retained `flight_declaration_raw_geojson`. Scan is bounded to 2,000 records; an incomplete scan stays unresolved. |
| `PUT /flight_declaration_ops/flight_declaration_state/{id}` | Activate, end, withdraw or cancel an owned declaration after reading its actual state. Verify the result by GET. |
| `PUT /flight_stream/set_telemetry` | Send operation observations with `flight_details.id` equal to the actual declaration UUID. Requires HTTP 201. |

State changes use read–write–read checks. Blender’s state endpoint does not provide an atomic compare-and-set contract; coordinate changes with other clients.

The SQLite record is saved before a creation request. A timeout, invalid response or interrupted process leaves submission unconfirmed. **Check status** searches for the same embedded reference and exact plan. A missing match does not prove that creation failed. Contact the service administrator if it remains unresolved; do not edit the database, discard it or create a replacement to bypass this check. Resolve the upstream record and preserve the audit trail before any recovery change.

Association is captured when each source sample enters the outbox, after a confirmed active state and within the declared window. Background checks refresh known declarations every 10 seconds; if status has not been verified for 30 seconds, new samples use the ordinary traffic route. Earlier queued samples are never relabelled. Bound samples use only their saved declaration, and the forwarder checks its state again before delivery. Samples outside an active declaration continue through the default traffic endpoint; they are not declaration telemetry.

Operation telemetry uses measured position, WGS84 altitude, take-off-relative elevation when present, source timestamp and horizontal speed when present. Position and speed accuracies remain unknown. Aircraft yaw is not ground track; track and vertical speed remain unknown using Blender’s sentinel values. Operator location and regulatory identifiers are not invented. This mapping does not assert ASTM RID compliance. The declaration panel shows its own acceptance, pending and gap counts, separate from general traffic status.

Back up the existing SQLite volume before upgrading. Startup adds an operation table and nullable sample association; old queued traffic remains unbound. Keep operation records and backups private: they contain pilot names, aircraft IDs and flight locations. Operation history is retained until an administrator applies an approved retention procedure; normal sample pruning still applies. To disable, finish active declarations and drain their queues first, then set `enabled` to `false` and restart. Any remaining bound samples are rejected, never converted into unrelated traffic.

Local automated tests use synthetic equipment and local contract receivers. They do not submit to a deployed Blender instance. Before rollout, complete the [optional declaration acceptance checks](acceptance.md#optional-declaration-workflow) against your release, exact Blender API and real controller.
