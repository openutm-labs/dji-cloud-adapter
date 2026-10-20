# Register equipment and manage access

[Home](../README.md) · [Deployment](deployment.md) · [Operations](operations.md)

For the service administrator. **There is no admin web form for invitations.** Run the commands below on the deployed service, or ask its hosting team to run them.

## Understand the two codes

| Code | Purpose | Lifetime |
|---|---|---|
| Invitation code | Registers one controller with one aircraft. | Administrator selects 1–168 hours; default 72 hours. |
| Connection code | Reconnects that registered equipment. | Retained until access is revoked or credentials change. |

Neither code is a personal account or proof of pilot identity. Serial numbers are read from Pilot 2 during registration. The administrator does not need the equipment or serial numbers in advance.

Registration supports **Mavic 3 Enterprise + RC Pro Enterprise** and **Matrice 400 + RC Plus 2 Enterprise Enhanced**, subject to acceptance of the exact firmware and payload.

## Enable enrollment

For a new service, complete the [deployment procedure](deployment.md). It uses `config.self-onboarding.example.json`, with `enrollment.enabled: true` and `devices: []`. Provisioning generates the broker's private enrollment credential.

For an existing service:

1. Back up its [application and broker state together](operations.md#consistent-backup).
2. Add `enrollment.enabled: true` and a random `mqtt.provisioner_password` of at least 32 characters to its private configuration.
3. Keep existing device entries and secrets.
4. Regenerate the broker bootstrap with `render-broker` and recreate app/broker in a maintenance window.

Preserve the broker volume. Its live dynamic-security state is authoritative after registration; do not replace it with an old bootstrap. The service provisions new equipment without restarting other pilots' connections.

<a id="administrator-issue-invitations"></a>

## Generate an invitation

The examples use `runtime/compose.env`. Use the deployed service's actual env file and Compose project. Commands run inside its app container, where `/config` is read-only and `/data` is persistent.

```sh
docker compose --env-file runtime/compose.env \
  -f compose.yml -f compose.production.yml \
  exec -T app dji-cloud-adaptor issue-invitation \
  --config /config/config.json --database /data/queue.sqlite3 \
  --label "Equipment setup 01" --hours 72 \
  --output /data/invitations/equipment-01.json
```

The command saves a private JSON file with `url`, `invitation_code` and `expires_at`. It does not print the code. The file uses mode 0600. Use a fresh output filename for each invitation.

An authorized administrator can retrieve it privately with:

```sh
umask 077
docker compose --env-file runtime/compose.env \
  -f compose.yml -f compose.production.yml \
  cp app:/data/invitations/equipment-01.json ./equipment-01.local.json
chmod 600 equipment-01.local.json
```

Open that private file. Send the **URL and invitation code** through the lab's private channel, with the expiry time. Do not put the code in a URL, screenshot or shared document. Issue a separate invitation for each pair, when the participant is ready.

## What the pilot does

1. Keeps the accepted aircraft on the ground and connected to its controller.
2. Opens the supplied URL in **Pilot 2 → Cloud Service → Open Platforms**.
3. Selects **First time here? Register this controller** and enters the invitation.
4. Selects the aircraft model and **Register and connect →**.
5. Keeps the generated connection code privately for later connections.
6. Completes the reception check with the coordinator.

No APK, personal OpenUTM signup or GitHub access is necessary. Give the complete [English](pilot-en.md) or [Spanish](pilot-es.md) procedure. Registration alone does not establish flight permission or data reception.

## Recover or remove access

Use the same deployment env/project as above. Replace `DEVICE_ID` with the enrolled ID from protected `/api/admin/status`. That endpoint needs the server's admin bearer token; keep it out of URLs and command arguments.

**Recover a lost connection code:**

```sh
docker compose --env-file runtime/compose.env \
  -f compose.yml -f compose.production.yml \
  exec -T app dji-cloud-adaptor export-device-code \
  --device DEVICE_ID --database /data/queue.sqlite3 \
  --output /data/recovery/device-01.json
```

Verify the recipient before delivering the recovered code. Retrieve the file privately using the same `cp` method as an invitation.

**Revoke a lost or retired enrolled device:**

```sh
docker compose --env-file runtime/compose.env \
  -f compose.yml -f compose.production.yml \
  exec -T app dji-cloud-adaptor revoke-device \
  --device DEVICE_ID --config /config/config.json --database /data/queue.sqlite3
```

Revocation blocks application sessions immediately. The running service refreshes its fleet within five seconds and retries broker reconciliation after outages. Closing the pilot page alone does not remove broker access.

**Cancel an unused invitation:**

```sh
docker compose --env-file runtime/compose.env \
  -f compose.yml -f compose.production.yml \
  exec -T app dji-cloud-adaptor revoke-invitation \
  --database /data/queue.sqlite3 \
  --invitation-file /data/invitations/equipment-01.json
```

Canceling an invitation does not revoke a registered device. Use `revoke-device` for that case.

## Resolve registration faults

| Condition | Action |
|---|---|
| Invitation expired before registration | Issue a replacement invitation. |
| Equipment already registered | Recover its connection code. An invitation cannot overwrite the pair. |
| Missing aircraft ID | Check power and controller connection on the ground. There is no manual-ID bypass. |
| License failure | Check DJI application credentials and actual-controller compatibility. |
| **Registration is saved** | Keep the pilot page open and retry **Register and connect**. Keep the same equipment and identity. |
| Replacement aircraft or controller | Arrange administrator-assisted reassignment. Do not invent another identity. |

For pre-provisioned devices in `config.json`, access changes require configuration/broker regeneration and app/broker restart; the enrolled-device commands above manage invitation registrations. Preserve pending data and back up the registry and broker together. See [operations](operations.md) and [protocol details](protocol.md#onboarding-handshake).
