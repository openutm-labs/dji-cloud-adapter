# Configure and host the adapter

[Home](../README.md) · [Pilot guide](pilot-en.md) · [Acceptance](acceptance.md)

This guide is for the service administrator. Pilots only need the connection URL and their controller's private code.

## Hosting requirements

Hosting is intentionally not selected yet. A small Docker-capable Linux VM is the simplest initial option because this service needs a continuously running MQTT connection, a persistent broker and a persistent SQLite volume. Do not deploy it as a stateless, request-only function.

Provide:

- A dedicated hostname with DNS pointing to the server, for example your chosen `cloud.<lab-domain>` address. Examples in this repository are placeholders, not deployed services.
- Public TCP 80/443 for HTTPS certificate issuance and HTTPS/WSS access. UDP 443 is optional HTTP/3 support.
- Outbound HTTPS access to Blender and its token issuer.
- Persistent private storage, backups, disk monitoring and a synchronised server clock.
- A trusted TLS certificate chain accepted by the actual controller firmware. Caddy automates certificate issuance; acceptance on Pilot 2 still needs testing. Do not work around a certificate warning by disabling verification.
- Docker Engine/Compose. Python 3.12+ and uv are used by the provisioning CLI on the administrator's workstation/server.

The supplied production Compose overlay exposes only Caddy. MQTT TCP, broker WebSocket and application ports remain internal. If that host already has a reverse proxy, adapt the routing with its administrator rather than binding a second proxy to occupied ports.

## 1. Prepare the private configuration

From the repository directory:

```sh
uv sync --frozen
cp config.example.json provisioning.local.json
chmod 600 provisioning.local.json
```

Edit `provisioning.local.json` privately:

1. Set `public_url` to the actual dedicated HTTPS address, without a subpath.
2. Set `workspace_name` to the lab name.
3. Set `dji.app_id`, `dji.app_key` and `dji.license` from the correct DJI **Cloud API** application. Licence verification occurs inside Pilot 2; having strings configured does not prove they are valid for this product/controller.
4. Set `mqtt.public_url` to `wss://<your-hostname>/mqtt`. The default internal `mqtt` host and port are for the provided broker.
5. Configure the confirmed Blender base URL and authentication. Use either `bearer_token` or the `oauth` object described in the [Blender contract](blender.md). Empty credentials prevent delivery and are shown as pending, rather than enabling anonymous uploads.
6. Replace the fictional controller/aircraft entries with exact physical serial numbers, aliases and model names. Add one device entry per controller. An aircraft cannot be assigned to two controllers in the same configuration.
7. Keep `allow_insecure_development` absent/false in production. Optional policy fields and their limits are defined in `config.py`.

Do not commit this input, actual serial-number inventories, private connection codes or runtime files. They are excluded by Git and Docker ignore rules.

Generate private configuration and broker grants:

```sh
uv run dji-cloud-adaptor init --input provisioning.local.json --output runtime
uv run dji-cloud-adaptor check --config runtime/config.json
```

The CLI refuses to overwrite an existing output directory. It creates:

| File | Purpose |
|---|---|
| `runtime/config.json` | Application settings and server-side credentials. |
| `runtime/controller-codes.json` | Per-controller private hand-off codes; deliver each code only to the assigned coordinator/device. |
| `runtime/broker/` | Broker passwords, ACLs and listener configuration. |
| `runtime/compose.env` | Host user/group IDs and the chosen domain; contains no API credentials. |
| `runtime/data/` | Persistent application database and WAL files. |

Files are created with mode 0600 and private directories with mode 0700. Use a dedicated non-root service owner on a Linux server. Compose runs the app with that owner's numeric user/group so it can read the private configuration and write its own data.

## 2. Start the production services

```sh
docker compose --env-file runtime/compose.env -f compose.yml -f compose.production.yml up -d --build
docker compose --env-file runtime/compose.env -f compose.yml -f compose.production.yml ps
```

Caddy serves the connection page over HTTPS and proxies `/mqtt` to the broker WebSocket listener. The broker converts its private bootstrap password file to hashed passwords at startup. Bootstrap inputs remain secrets and must remain private.

Use **one app process** per database. Do not increase Uvicorn workers or horizontally replicate this SQLite-backed service. Deploy separate lab instances initially.

## 3. Verify before giving the link to pilots

- The HTTPS page loads with a valid certificate on the actual controller.
- `/healthz` returns 200 when the application/database can respond.
- `/readyz` returns 200 only when MQTT subscription, forwarding loop and required credential fields are configured. This is a readiness check, **not a live licence/token/aircraft verification**.
- Anonymous requests cannot read `/api/pilot/bootstrap`, configuration, status or `/api/admin/status`.
- The real Pilot 2 licence check and per-controller connection succeed.
- A recent aircraft position reaches Blender and is verified downstream.

Then complete the [acceptance checklist](acceptance.md). Share the [English](pilot-en.md) or [Spanish](pilot-es.md) guide, HTTPS address and the device's code privately. Never share the admin token or Blender credentials with pilots.

## Local development

Use a **separate** private input/configuration for development:

- `public_url`: `http://localhost:18080`
- `mqtt.public_url`: `ws://localhost:19001/mqtt`
- `allow_insecure_development`: `true`
- Keep the broker's internal host as `mqtt` when running the application in Compose.

```sh
docker compose --env-file runtime/compose.env -f compose.yml -f compose.development.yml up -d --build
```

This exposes only loopback ports 18080 (web), 18884 (MQTT TCP) and 19001 (MQTT WebSocket). The development overlay mounts web assets for UI editing. A regular browser displays instructions and disables native connection; it cannot simulate a DJI aircraft.

Do not point a development simulator at Panama's operational Blender. The automated tests use synthetic aircraft and a local HTTP receiver. Test-only plaintext URLs are restricted to loopback/known Docker development hosts.

## Operations, access changes and recovery

- Monitor `/readyz`, broker availability, disk space and protected queue status. The `/api/admin/status` endpoint requires the private `admin_token` as a bearer token. Do not put it in a URL or publish its response.
- Restart app and broker after editing the configuration or access grants. Run `uv run dji-cloud-adaptor render-broker --config runtime/config.json --output runtime/broker` before restarting when device assignments/passwords change.
- To revoke a lost controller, remove its entry, regenerate broker files and restart **both app and broker**. The restart terminates existing MQTT connections; removing a password file entry alone does not necessarily disconnect an established client. Removed devices' queued samples are rejected rather than forwarded.
- To replace a device's connection code, generate a fresh random code/hash and MQTT password through a newly prepared private configuration and securely deliver the replacement. Never reuse another controller's credentials. Session records bind to the connection-code hash and become invalid when it changes and the application reloads.
- Do not rerun `init` over an existing lab directory or delete its database to solve an update. Preserve settings, traffic session IDs, pending samples and controller code assignments.
- On Blender downtime, the queue retries recent samples. Older ones become `expired` and remain locally until retention pruning; they must not be manually replayed into a live feed. Ask the Blender team for an agreed historical-ingestion path if historical recovery is needed.
- Default retention is seven days; set `retention_days` under the lab's policy. Queue/database files contain location history and private identifiers. Protect backups accordingly. Stop the application for a filesystem backup, or use SQLite's backup API; do not copy only the database file while ignoring an active WAL.
- HTTP delivery is at least once. A crash/lost response after remote acceptance can duplicate a sample downstream; use `source_event_id` for diagnosis and agree server idempotency if needed.

## Still required for Panama

Hosting/domain selection, confirmed physical controller/aircraft/payload/firmware, Blender credentials and classification decisions, controller TLS/licence acceptance, and a supervised end-to-end check. No hosting purchase, DNS change or production deployment has been performed.
