# DJI adaptor software acceptance — 19 October 2026

[Procedure](../simulation.md) · [Operations](../operations.md) · [Checklist](../acceptance.md)

**Result: local simulated pipeline passed; hosted writes and public deployment incomplete.**
No aircraft/controller, flight declaration, flight-control action or operational record
cleanup was used. Existing private runtime credentials were reused without publishing
them. The Apache 2.0 licence is unchanged, and examples remain deployment-neutral.

## Evidence by boundary

| Boundary | Result | Evidence and limit |
|---|---|---|
| Upstream simulator | Reviewed, not adopted | Source pinned at `2db9ea4c9b25878c41fa5a30c42aec903e89f1a6`; envelope, Dock model codes, auth/TLS, permissions and altitude differences documented. No source copied or executed. |
| Simulator → broker | Passed locally | Fictional `SIM-...` equipment; password authentication, exact ACLs, TCP/WebSocket and WSS. Wrong passwords and command/other-aircraft publishing denied. |
| Broker → adaptor | Passed locally | Correlated topology receipt, current enveloped OSD, invalid/raw/partial/stale/retained rejection, duplicate suppression, persistent SQLite queue. |
| Adaptor → local receiver | Passed | Built image, Caddy HTTPS/WSS with explicit CA trust and default untrusted-TLS rejection. OAuth client-credentials exchange and bearer-authenticated HTTP ingestion into a test-only receiver. |
| Independent local readback | Passed | Three separate GET matches; latitude/longitude, ellipsoid metres ×1000, relative elevation, original source milliseconds, source classification, run/session/address/event IDs. SQLite event IDs/times match readback. **Receiver is not hosted Flight Blender.** |
| Recovery/faults | Passed locally | 401/403/503 injection, OAuth renewal, expiry without live replay, pending-queue app restart, broker restart/reconnect, duplicates across restart, persistent enrolled-device revocation. TLS-path broker/app restarts preserve accepted records. |
| Real hosted OAuth/read | Passed | Certificate verification enabled; token acquisition and protected health/read queries work, anonymous protected health returns 401. [Sanitised preflight](2026-10-19-hosted-preflight.json). |
| Real hosted write | Incomplete | No telemetry POST issued. No documented sandbox or agreed reserved classification/consumer exclusion supplied. A session UUID is not traffic isolation. Token credentials alone do not resolve this requirement. |
| Real downstream persistence | Incomplete | Protected query is accessible, but no synthetic record was submitted or independently matched there. Worker processing/persistence cannot be inferred from preflight. |
| Real dashboard | Incomplete | Home page is available; no dashboard/homebase route is documented in fetched OpenAPI. Probed `/homebase` and `/realtime` return 404. A separate display URL/access and isolated test traffic are still needed if dashboard acceptance is required. |
| Hosted adaptor | Incomplete | Local Docker available; no adaptor host/domain allocated. Unrelated connected cloud resources were not changed. No public URL/deployed commit, DNS change or spending. |
| DJI hardware | Untested | Native Pilot 2 licence, physical controller/aircraft/firmware/payload, TLS trust and actual packets remain hardware acceptance. Simulation does not establish flight readiness or ASTM RID compliance. |

The hosted contract SHA-256 is
`6a9d1460aca5f7265bef54181cb57230086bf3031d8db4235955eaf143761d96`.
Deployed write/read routes and the integer source/metadata schema were inspected.
Matching workspace source shows that traffic GET uses the URL UUID as a reader cursor
over shared observations and does not provide a writer-session filter. Treat this as
an implementation review, not a guarantee of undocumented isolation in the service.

## Reproducible checks

```sh
uv run ruff check src tests
uv run ruff format --check src tests
docker build -t dji-cloud-adaptor-app .
RUN_MQTT_INTEGRATION=1 RUN_STACK_INTEGRATION=1 uv run pytest -q
node --test tests/portal.test.cjs
```

Full suite: **88 Python tests passed** with broker/stack integration enabled;
**14 Node tests passed**. Ruff, formatting, dependency export, Compose release validation
and shell syntax checks passed. The known Starlette/httpx test-client deprecation
warning remains. The final strengthened TLS/OAuth/outbox test was rerun separately.
CI runs the simulator and TLS stack tests as well. Check the GitHub run for the commit
containing this report before deployment; local results alone are not a hosted release.

The [local TLS manifest](2026-10-19-local-tls.json) contains only fictional simulation
identifiers, timestamps and coordinates. Its `target_kind=local_contract_receiver`
explicitly limits `downstream_verified=true` to that fixture. These are generated
current timestamps, not canned observations submitted with stale times. Test source
255 is allocated **only by the local fixture**, not by the real service.

Publisher clients disconnect at the end of every test, and owned test containers,
networks and receiver records are removed. Private runtime configuration and unrelated
containers are preserved. No hosted test records exist from this continuation, so no
shared-service cleanup was attempted. Hosted observation retention/deletion must be
agreed before the eventual write test; no observation-delete endpoint is documented.

## Remaining decisions and access

1. Obtain a dedicated test Blender instance or an owner-confirmed reserved simulation
   source and exclusion from all operational consumers. Record its actual allocation
   and test-record retention/cleanup agreement. Then run up to three observations and
   verify independent records; do not stop at HTTP 201/202.
2. Allocate an authorised Docker host and dedicated DNS name. The prepared architecture
   uses persistent app/broker/Caddy data, pinned dependencies, private credentials and
   restart policies. A 2 GiB / 1 vCPU Linux VM is the recommendation; the referenced
   provider price is US$12/month before domain/backups/tax, subject to the owner's decision.
3. Build the committed image with `deploy/build-release.sh`, deploy that immutable
   package, establish monitoring/backup ownership, test host reboot/restore, and repeat
   the three-point test through public HTTPS/WSS. Record URL, image ID/digest and full
   deployed commit only after this succeeds.

The release builder archives committed files only, excludes ignored runtime state and
labels/saves the exact Git revision and image ID. Backup, paired restore and rollback
steps are documented; an actual host backup/restore rehearsal remains unperformed.
