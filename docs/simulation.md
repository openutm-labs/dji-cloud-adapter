# Reproduce software integration without DJI equipment

[Home](../README.md) · [Acceptance](acceptance.md) · [Operations](operations.md)

This harness tests a receiver contract. It does not emulate Pilot 2's native bridge,
verify a DJI licence, certify a model/firmware combination, or establish flight readiness.
It is never started by Compose or the application. Broker authentication and production
payload validation remain enabled.

## Simulator investigation

Reviewed [YuYongJu/dji-cloud-simulator](https://github.com/YuYongJu/dji-cloud-simulator/tree/2db9ea4c9b25878c41fa5a30c42aec903e89f1a6)
at **`2db9ea4c9b25878c41fa5a30c42aec903e89f1a6`**, 19 October 2026.
Its MIT licence credits Copyright (c) 2026 Panoptris. No code was copied, vendored,
executed or installed; this repository and its original harness remain Apache 2.0.
To reproduce the source inspection, clone separately and detach at that full revision.

| Area | Pinned upstream source | Receiver/harness decision |
|---|---|---|
| OSD envelope | `publishOsd` sends raw properties, without `data`, `timestamp` or `gateway`. | DJI's [topic examples](https://github.com/dji-sdk/Cloud-API-Doc/blob/4ec6b0c7f9472aeb09a0a47949855d19c473ea07/docs/en/60.api-reference/10.pilot-to-cloud/00.mqtt/00.topic-definition.md) define an envelope. Keep receiver rejection; generate the envelope. |
| Equipment | Advertises Dock 2/M30T; online topology sets gateway and child to aircraft codes `0/60/1`. | Those are not our Pilot 2 equipment. Use a minimal assigned-identity topology fixture and omit unverified model codes. Numeric model validation and native topology still need hardware packets. |
| Authentication/TLS | Connects using broker URL and no explicit username/password or trusted-CA settings. URL credentials would expose secrets through arguments/logging. | Read device credentials privately. Accept verified `mqtts`/`wss`; plaintext only on loopback/development broker names. No URL credentials or TLS bypass. |
| Permissions | Subscribes to services and publishes successful command replies and other Dock topics. | Publish only assigned topology/OSD; subscribe only to the topology receipt. Commands and other aircraft remain denied by ACLs. |
| Altitude | Generated `height=altitude`, `elevation=altitude+10` without a configured geographic datum. | DJI's [M3 property definitions](https://github.com/dji-sdk/Cloud-API-Doc/blob/4ec6b0c7f9472aeb09a0a47949855d19c473ea07/docs/en/60.api-reference/10.pilot-to-cloud/00.mqtt/10.m3-series/00.properties.md) distinguish ellipsoid height from take-off-relative elevation. Generate explicitly separate values. |
| Boundaries | Patrol is continuous and scenarios include HMS/mission/command handling. | Maximum three samples, at least two seconds apart, finite readback waits, disconnect on completion/failure. |

## Local acceptance

```sh
uv sync --frozen
docker build -t dji-cloud-adaptor-app .
RUN_MQTT_INTEGRATION=1 RUN_STACK_INTEGRATION=1 uv run pytest -q
node --test tests/portal.test.cjs
```

The tests create private ephemeral runtimes and only their own Docker resources. They
exercise real Mosquitto passwords/ACLs, TCP/WebSocket, invalid/raw/partial/stale/retained
messages, duplicates across restart, reconnect, revocation, expiry, local 401/403/503
faults, and pending-queue recovery. No fault injection contacts a shared service.

`test_simulation_stack.py` builds the full path through the shipped Caddy routing,
with a private test CA explicitly trusted by the client. Default untrusted TLS fails.
The built app runs read-only with its persistent data mount. Three positions traverse
WSS → authenticated Mosquitto → app/outbox → OAuth-authenticated local HTTP receiver, and are read through
independent GET requests. This receiver is a **test double, not Flight Blender**.
`/.integration-runtime/last-tls-acceptance.json` records the most recent run privately.

The fixture source code **255 is local-only**. It is not an assigned Blender standard,
not an ASTM RID category, and not approval to submit it to another deployment.

## Inspect a real target without writing

Use the existing private runtime's OAuth settings. Do not paste credentials into a command:

```sh
uv run python -m dji_cloud_adaptor.simulator inspect-blender \
  --config runtime/config.json --report runtime/preflight.json
```

This fetches the deployed OpenAPI contract, checks anonymous denial, acquires a token,
and checks protected health and traffic reads with TLS verification. It saves only
statuses, route availability and the OpenAPI SHA-256, never API response bodies or
unrelated observations. It performs no traffic POSTs. An OpenAPI schema accepting an
integer is not proof that an arbitrary source code has agreed display semantics.

## Establish isolation before a real write

A UUID in `set_air_traffic/{session_id}` identifies submitted observations. In the
reviewed Blender implementation, `get_air_traffic/{session_id}` uses that UUID as a
reader cursor over shared traffic; it does **not** filter by the writer session.
Its current bbox implementation orders coordinates as latitude,longitude despite
conventional minx/miny wording. The fixture query matches that implementation.
Review this again if the deployed schema/version changes.

Use an isolated test instance, or have the service owner allocate a simulation source
code outside existing real-surveillance categories 0–11 and exclude it in **all**
operational consumers, alerts and displays. Our metadata alone does not enforce that
exclusion. Do not create declarations to obtain a test namespace. If isolation cannot
be established, complete read-only preflight and mark real-write acceptance incomplete.

Record the actual allocation privately in `runtime/isolation.local.json`:

```json
{
  "base_url": "https://blender.example.org",
  "traffic_source": 255,
  "operational_consumers_exclude": true,
  "allocation_reference": "Replace with the service owner's actual test allocation and exclusion evidence"
}
```

255 above remains a placeholder until allocated. The harness checks this note against
the configured target and code both when preparing and running. The note documents an
external agreement; it cannot configure or prove filters in another service.

## Prepare and run against an isolated target

```sh
uv run python -m dji_cloud_adaptor.simulator prepare \
  --config runtime/config.json --output runtime/simulation-01 \
  --traffic-source 255 --isolation-file runtime/isolation.local.json
```

This refuses overwrite and creates an independent fleet, workspace, admin/MQTT secrets,
SQLite directory, broker grants and Compose environment. It reuses the supplied
Blender authentication and DJI configuration without printing them. It neither changes
the source runtime nor validates its DJI licence. No connection code usable for
production onboarding is generated.

Edit the new private config's public HTTPS/WSS addresses for the dedicated acceptance
host. Set `allow_insecure_development=false` and validate it. Use the generated
`ADAPTOR_RUNTIME` and distinct `COMPOSE_PROJECT_NAME` with the deployment instructions;
do not replace an existing runtime or share its broker volume. The resulting service
uses the same app/broker/proxy architecture. Keep the publisher on the test workstation.

After deploying the reviewed image, check public `/readyz`, certificate hostname/trust
and anonymous endpoint denial. Then run through the configured public WSS endpoint:

```sh
uv run python -m dji_cloud_adaptor.simulator run \
  --config runtime/simulation-01/config.json \
  --isolation-file runtime/isolation.local.json \
  --count 3 --report runtime/simulation-01/public-run.json
```

For local debugging only, `--mqtt-url mqtt://localhost:18884` or
`--mqtt-url ws://localhost:19001/mqtt` selects the loopback listener. A local private CA
may be supplied with `--ca-file`; there is no insecure certificate option.
`--publish-only` skips readback and therefore does **not** establish acceptance.

Every packet gets its current source time. Correlate `simulation_run_id`, stable
aircraft/session IDs, `source_event_id`, coordinates, millimetre altitude and the
original timestamp across the outbox and independent protected GET results. Readback
checks metadata `source_timestamp_ms` because the reviewed traffic GET omits the
original sensor timestamp; it does not claim a direct inspection of the target's
database timestamp column. It checks `123.456 m → 123456 mm`, distinct relative
elevation, `simulation=true`, simulation source, reserved code, and no RID compliance.

The run uses fictional `SIM-RC-...` / `SIM-M3E-...` serials, `SIMULATION ...` names,
24-character `sim-dji-...` opaque IDs, UUID run/session IDs and a small Pacific-ocean
fixture area. These markers come from server configuration, not untrusted OSD fields.
Metadata is filterable; geographic distance alone is not isolation.

Success requires every expected observation to match a separate query. A 201, a
topology receipt, or a green status is insufficient. Failure saves the partial report,
returns nonzero and disconnects the publisher. Do not restart with old timestamps or
replay expired samples. For a new acceptance run, prepare a new runtime/run ID.

## Record lifetime and cleanup

Local tests remove their own containers, volumes and receiver records. Sanitised
evidence files remain in the ignored integration directory. The adaptor retains
outbox records for its configured retention (seven days by default).

The reviewed deployed API documents no observation-delete endpoint or guaranteed
traffic retention. Live traffic queries show recent rows; disappearance from a live
query is **not** deletion. Agree test-record retention/cleanup with the service owner
using the exact run/session/address markers before publishing. Do not delete unrelated
rows, send undocumented cleanup calls, or infer downstream retention from our outbox.
If a dashboard is supplied separately, verify its filtered test display independently;
an API query does not prove a dashboard rendered the record.
