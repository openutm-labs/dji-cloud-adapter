# Deploy the adapter

[Home](../README.md) · [Admin tasks](self-onboarding.md) · [Operations](operations.md) · [Acceptance](acceptance.md)

For the hosting and Blender teams. Deploy the full stack: **Caddy, Mosquitto and the adapter**. A Docker-capable Linux VM with persistent disk is suitable. A DigitalOcean Droplet is one option. Use one application process per SQLite database.

## Agree the deployment inputs

| Input | Owner to identify |
|---|---|
| Host, dedicated DNS name, backups and monitoring | Hosting team |
| DJI Cloud API application ID, key and license | DJI application owner |
| Blender URL, OAuth client, scopes and traffic classification | Blender team |
| Accepted equipment, ground check and permitted activity | Equipment / operations lead |
| Invitations, recovery and support contact | Onboarding administrator |

The DJI license must match this Cloud API product and pass on the actual controller. Configured credentials alone do not establish acceptance.

For a small assisted trial, 2 GiB RAM / 1 vCPU is a starting size; monitor actual usage. Configure:

- DNS pointing to the host and a trusted public TLS certificate.
- Public TCP 80/443 and restricted SSH. UDP 443 is optional.
- Outbound HTTPS to Blender and its token issuer, plus DNS and certificate issuance access.
- Persistent private storage and a synchronized clock.
- Docker Engine/Compose, Python 3.12+ and uv for provisioning.

Pilot 2 connects through `wss://<hostname>/mqtt`. The supplied Caddy proxy routes this to Mosquitto internally. Do not expose broker ports 1883/9001 or application port 8080 publicly. If the host already has a proxy, agree equivalent HTTPS/WebSocket routing with its owner.

## 1. Prepare a new service

Run as a dedicated non-root service owner, from the reviewed repository checkout:

```sh
uv sync --frozen
cp config.self-onboarding.example.json provisioning.local.json
chmod 600 provisioning.local.json
```

Complete the private input file:

| Setting | Value |
|---|---|
| `public_url` | Actual HTTPS address, without a subpath. |
| `workspace_name` | Lab or organization name. |
| `dji.app_id`, `dji.app_key`, `dji.license` | Correct DJI Cloud API application values. |
| `mqtt.public_url` | `wss://<hostname>/mqtt`. Keep internal broker host `mqtt`. |
| `blender` | Confirmed base URL and OAuth settings from the [Blender contract](blender.md#server-configuration). Agree source classification. |
| `enrollment.enabled` / `devices` | `true` / `[]` for invitation-based registration. |
| `allow_insecure_development` | Absent or `false`. |

Keep credentials and runtime files private. For fixed, pre-provisioned equipment, use `config.example.json` instead and replace its fictional device entries with the actual pairs.

```sh
uv run dji-cloud-adaptor init --input provisioning.local.json --output runtime
uv run dji-cloud-adaptor check --config runtime/config.json
```

`init` creates private configuration, broker grants, `compose.env` and a data directory. It refuses an existing output directory. **Do not rerun it over a live service.** Existing installations use the [enrollment migration](self-onboarding.md#enable-enrollment) and [backup procedure](operations.md#consistent-backup).

## 2. Start the stack

For initial setup, build and start the reviewed source:

```sh
docker compose --env-file runtime/compose.env \
  -f compose.yml -f compose.production.yml up -d --build
docker compose --env-file runtime/compose.env \
  -f compose.yml -f compose.production.yml ps
```

For an operational release, use the [immutable-image procedure](operations.md#release-package), which adds `compose.release.yml` and records the deployed image. Match the image architecture to the host.

Keep the same Compose project name for this deployment. Record it with the runtime path. Set `COMPOSE_PROJECT_NAME` in its private Compose env if needed to keep the name stable across release directories. `ADAPTOR_RUNTIME` can select an absolute private runtime path; set `ADAPTOR_UID/GID` to its Linux owner. Private directories use mode 0700 and files 0600.

## 3. Verify the service

1. Make sure that HTTPS and `/mqtt` use the correct hostname and trusted certificates.
2. Make sure that `/healthz` and `/readyz` return 200.
3. Run the read-only Blender access check:

```sh
docker compose --env-file runtime/compose.env \
  -f compose.yml -f compose.production.yml \
  exec -T app dji-cloud-adaptor check-blender --config /config/config.json
```

4. Make sure that anonymous requests cannot read pilot bootstrap, private status or admin diagnostics.
5. Configure readiness, disk and backup alerts with a named owner.
6. Arrange the [actual-controller acceptance check](acceptance.md#required-on-each-real-equipment-combination).

Use the actual deployment's env file and Compose project for service commands. Readiness and a protected GET do not prove traffic writes, DJI licensing or downstream storage. Keep TLS verification enabled. Synthetic writes require an [isolated test context](simulation.md#establish-isolation-before-a-real-write).

## 4. Hand over for an assisted ground check

Give the onboarding administrator the HTTPS address, deployed commit/image, service owner and outstanding acceptance items. Arrange access to the [invitation command](self-onboarding.md#generate-an-invitation); there is no admin web form for it.

Issue one private invitation per controller–aircraft pair when the participant is ready. Share the pilot guide in [English](pilot-en.md) or [Spanish](pilot-es.md). Complete the supervised reception check before accepting the setup. Keep personal identity, declarations and operating permissions in the lab's separate procedure.

## Local development

Use separate configuration, credentials and data. Set `public_url` to `http://localhost:18080`, `mqtt.public_url` to `ws://localhost:19001/mqtt`, and `allow_insecure_development` to `true`.

```sh
docker compose --env-file runtime/compose.env \
  -f compose.yml -f compose.development.yml up -d --build
```

Only loopback ports 18080, 18884 and 19001 are exposed. A browser preview cannot connect an aircraft. Use [operations](operations.md) for backups and upgrades, [admin tasks](self-onboarding.md) for access changes, and the [protocol reference](protocol.md#validation-and-delivery) for queue and delivery behavior.
