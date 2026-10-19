# Invite operators to register their own equipment

[Home](../README.md) · [Hosting](deployment.md) · [English pilot steps](pilot-en.md) · [Pasos del piloto en español](pilot-es.md)

This route is for **Mavic 3 Enterprise + RC Pro Enterprise** and **Matrice 400 + RC Plus 2 Enterprise Enhanced**, running an approved Pilot 2/firmware/payload combination. The administrator can issue an invitation without knowing serial numbers or possessing the equipment. The operator completes setup later on the actual controller.

The invitation authorises one equipment registration. It is not account sign-in, proof of pilot identity, hardware attestation or flight approval. The operator selects the aircraft model; Pilot 2 supplies the controller and connected aircraft serials. The server checks identity consistency and uniqueness, not manufacturer-signed ownership. Continue the organisation’s pilot, equipment acceptance and operating-permission checks separately.

## Operator journey

1. Receive the organisation’s hosted HTTPS address and a private, unexpired **invitation code**. Each controller/aircraft pair needs its own invitation. An operator with both equipment combinations uses two invitations.
2. With the aircraft on the ground, power on and link the approved equipment. Open the address in **Pilot 2 → Cloud Service → Open Platforms**.
3. Select **First time here? Register this controller** / **¿Primera vez? Registre este controlador**.
4. Enter the invitation, select the exact aircraft model and optionally give the controller a useful nickname. Do not enter account passwords or developer credentials.
5. Select **Register and connect →** / **Registrar y conectar →**. The page verifies the DJI licence, reads both serials and registers the pairing. Operators do not need to type or send serials in advance.
6. Save the new **connection code** privately. It belongs to this controller and replaces the invitation for later connections. It is hidden until **Show code / Mostrar código**; do not photograph it or share it with another controller.
7. Check controller connection, aircraft telemetry and Blender acceptance as described in the pilot guide. Registration alone does not prove any of those connections or operational approval.

No APK, command line or access to GitHub is needed on the controller. The service must be hosted at an address the controller can reach; a localhost browser preview cannot register real equipment. Registration is limited to the supported equipment combinations; it does not add compatibility to other aircraft or controllers. Keep server-side Blender credentials private.

## Service owner: enable once

For a new service, copy `config.self-onboarding.example.json` to a private `*.local.json` file and complete the public HTTPS/WSS addresses, DJI application fields and Blender OAuth fields using the deployment guide. Keep `devices: []` when no equipment has registered. `init` generates the private broker provisioner credential automatically when `enrollment.enabled` is true.

```sh
uv run dji-cloud-adaptor init --input provisioning.local.json --output runtime
uv run dji-cloud-adaptor check --config runtime/config.json
```

For an existing installation, back up the private configuration, SQLite database and broker volume before migration. Add `enrollment.enabled: true` and a separate random broker provisioner password of at least 32 characters to private `mqtt.provisioner_password`. Keep existing real device entries and secrets. Regenerate the broker bootstrap with `render-broker`, then recreate the broker and app in a supervised maintenance window. Do not replace a live runtime or delete its broker volume to migrate.

Enrollment uses Mosquitto's dynamic-security plugin, included in the supplied broker image. The private initial JSON is copied into the broker's persistent data volume only on first bootstrap. Subsequent broker restarts keep that authoritative live state. Do not replace it with an old bootstrap after operators have registered. See [Mosquitto dynamic security](https://mosquitto.org/documentation/dynamic-security/) and its [2.1.2 control protocol](https://github.com/eclipse-mosquitto/mosquitto/blob/v2.1.2/plugins/dynamic-security/README.md).

The service generates exact per-device topic permissions and refreshes the worker's subscriptions during registration; it does not restart other pilots' connections. Only the separate server-side provisioner can access the broker-control topic. Pilot and telemetry-worker roles cannot publish aircraft commands or broker-control messages. The worker has access only to registered aircraft/status topics.

## Administrator: issue invitations

On the service host, with access to its private runtime:

```sh
uv run dji-cloud-adaptor issue-invitation \
  --config runtime/config.json \
  --database runtime/data/queue.sqlite3 \
  --label "Operator setup" --hours 72 \
  --output runtime/invitations/operator-01.json
```

Use a fresh filename per invitation. The file is created with mode 0600; the command does not print the code. Send the correct environment's HTTPS address and its invitation code through the organisation’s approved private channel. No serial inventory is required. Each invitation lasts up to seven days and registers one controller with one aircraft; issue it when the operator is ready. Do not create invitations just to distribute them publicly or include them in documentation, screenshots or URLs.

Inside Docker, use the same CLI with `--config /config/config.json` and `--database /data/queue.sqlite3`; choose an output under `/data/` because the config mount is read-only. Treat that output as a secret and transfer it privately. Do not publish invitation files as shared downloads.

## Retry, recovery and revocation

- **No aircraft ID:** keep the aircraft on the ground, powered and linked. The bridge must expose both serials; there is no manual-ID bypass on the operator page. Confirm the Pilot 2 version if it still fails.
- **Licence failure:** no equipment registration occurs; ask the service owner to verify the DJI application and hardware compatibility.
- **Service temporarily unavailable:** the reserved registration is durable. Keep the page open and retry **Register and connect**. The same invitation can resume a pending reservation until expiry, but cannot register different equipment.
- **Equipment already registered:** use its existing connection code. Do not register it under a different serial, model or identity. Support must verify ownership before recovery or reassignment.
- **Invitation expired/used:** a completed registration uses its saved device code. For unused invitations, request a replacement through the administrator.
- **Lost connection code:** an authorised administrator can use the protected admin status to find the device ID and recover its code to a private file:

```sh
uv run dji-cloud-adaptor export-device-code --device DEVICE_ID \
  --database runtime/data/queue.sqlite3 --output runtime/recovery/device.json
```

Revoke a lost/retired registered device:

```sh
docker compose --env-file runtime/compose.env -f compose.yml -f compose.production.yml \
  exec -T app dji-cloud-adaptor revoke-device --device DEVICE_ID \
  --config /config/config.json --database /data/queue.sqlite3
```

Use `compose.development.yml` for the local stack. The command runs inside the app container so it can reach the internal broker hostname. This records revocation before disabling the broker client. API logins/sessions reject the revoked device immediately; the running service refreshes the registered fleet within five seconds and retries broker reconciliation after outages. Do not tell an operator that closing a web page revokes MQTT credentials. Replacing an aircraft/controller pairing currently needs administrator-assisted reassignment; an invitation cannot overwrite an existing registration.

Cancel an unused invitation from its private hand-off file:

```sh
uv run dji-cloud-adaptor revoke-invitation \
  --database runtime/data/queue.sqlite3 --invitation-file runtime/invitations/operator-01.json
```

Cancelling an invitation does not by itself revoke an already registered device; use `revoke-device` too when required.

## Backups and acceptance

Back up the app's SQLite database (including a consistent WAL snapshot), its private runtime configuration and the broker's persistent dynamic-security data together. The database contains device connection codes/MQTT passwords as well as registration records and therefore must remain private. Invitation codes and temporary enrollment-session tokens are stored as hashes. Restore must preserve both registry and broker state; practise restore before operational use. Use one app process per SQLite database.

Local tests cover invitation expiry, replay, duplicate equipment, both models, failed provisioning/retry, persistence, revocation, exact broker permissions and registration from an empty fleet without a restart. Portal tests cover automatic IDs, missing aircraft, licence failure, safe retry and connection-code recovery after native connection failure. They use fictional devices and local receivers. Actual controllers, DJI licence/TLS trust, hosted registration and real Blender ingestion remain acceptance requirements.
