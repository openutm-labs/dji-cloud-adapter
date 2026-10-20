# Panama service: connect and administer

[Home](../README.md) · [English pilot guide](pilot-en.md) · [Guía del piloto en español](pilot-es.md) · [Admin reference](self-onboarding.md)

**Connection address:** [https://dji-cloud-api.panama.openutm.net/](https://dji-cloud-api.panama.openutm.net/)

Server checks passed on **20 October 2026**. The service is available for an assisted ground check. Actual-controller licensing, registration and aircraft telemetry reception remain pending.

## Connect equipment

1. Get a private invitation from the coordinator, or the saved code for registered equipment.
2. Keep the accepted aircraft on the ground and connected to its controller.
3. Open **DJI Pilot 2 → Cloud Service → Open Platforms**.
4. Enter `https://dji-cloud-api.panama.openutm.net/`.
5. Complete the [English](pilot-en.md#register-or-reconnect) or [Spanish](pilot-es.md#registrar-o-reconectar) registration/reconnection steps.
6. Complete that guide's reception check with the coordinator.

Keep the generated connection code privately for later use. No OpenUTM APK or personal OpenUTM signup is necessary. Equipment connection does not establish flight permission.

## Issue an invitation

An authorized administrator needs SSH access as `dji`. On the server:

```sh
cd /home/dji/dji-cloud-adapter
./runtime/stack exec -T app dji-cloud-adaptor issue-invitation \
  --config /config/config.json --database /data/queue.sqlite3 \
  --label "Panama equipment 01" --hours 72 \
  --output /data/invitations/equipment-01.json
```

Retrieve the private handoff file on the server:

```sh
umask 077
./runtime/stack cp app:/data/invitations/equipment-01.json ./equipment-01.local.json
chmod 600 equipment-01.local.json
```

Open the file privately. Send its `url` and `invitation_code`, with the expiry time, through the lab's private channel. Use a fresh filename for each invitation. Each invitation registers one controller–aircraft pair. There is no admin web form. See [recovery and revocation](self-onboarding.md#recover-or-remove-access); use `./runtime/stack` in place of those examples' Compose prefix.

## Verify the service

```sh
./runtime/stack ps
./runtime/stack exec -T app dji-cloud-adaptor check-blender \
  --config /config/config.json
```

| Check | Verified result on 20 October |
|---|---|
| Connection page, `/healthz`, `/readyz` | HTTP 200; readiness checks all true. |
| `wss://dji-cloud-api.panama.openutm.net/mqtt` | Trusted TLS and authenticated broker connection. |
| Blender access check | OAuth token acquisition and protected GET succeeded. |
| Private pilot/admin endpoints | Anonymous requests returned HTTP 401. |

No application messages or traffic observations were published during server verification. A healthy server does not prove DJI license validity or downstream storage. Complete the [real-equipment acceptance procedure](acceptance.md#required-on-each-real-equipment-combination) before accepting a pair for the intended activity.

## Maintain the deployment

The current route is:

```text
Nginx/Certbot HTTPS → loopback Caddy :3000 → app :8080 or MQTT WebSocket :9001
```

Use `/home/dji/dji-cloud-adapter/runtime/stack` for every Compose operation. It selects `compose.yml`, `runtime/compose.host-proxy.yml` and the correct env/project. Do not add `compose.production.yml` on this host; its public ports conflict with existing Nginx.

The private `runtime/deployment-record.json` records the active image and backup location. `runtime/OPERATIONS.md` holds host instructions. Preserve runtime and broker state during upgrades. Use the [backup and restore procedure](operations.md#consistent-backup) with the deployed wrapper; do not delete volumes or rerun initialization over this service.
