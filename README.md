# DJI Cloud Adapter for OpenUTM

Send aircraft position and status from **DJI Pilot 2 to Flight Blender**. Pilots keep Pilot 2 as the flight application. No OpenUTM APK or personal OpenUTM signup is needed for this equipment connection.

**Status:** the local simulated pipeline and hosted Blender reads have been tested. Public deployment, real-target writes and actual-controller acceptance remain pending. See [acceptance evidence](docs/acceptance.md).

## What must be deployed

```text
Pilot 2 → MQTT broker → Adapter → Flight Blender API
```

Deploy the complete Docker stack on a Linux host with persistent storage:

| Component | Purpose |
|---|---|
| Caddy | Serves the HTTPS connection page and secure WebSocket endpoint. |
| Mosquitto MQTT broker | Receives telemetry from Pilot 2. |
| Adapter | Validates telemetry, queues recent samples and forwards them to Blender. |

All three can run on one DigitalOcean Droplet. The production configuration exposes web access on ports 80/443. Pilot 2 uses `wss://<hostname>/mqtt`; broker and application ports stay internal. [Deployment procedure](docs/deployment.md)

## Choose your task

| Reader | Start here |
|---|---|
| Hosting or Blender team | [Deploy the service](docs/deployment.md), then complete [acceptance](docs/acceptance.md). |
| Administrator | [Generate invitations, recover codes and remove access](docs/self-onboarding.md). Invitation generation currently uses a server command; there is no admin web form. |
| Pilot or operator | [Connect in English](docs/pilot-en.md) · [Conectar en español](docs/pilot-es.md). |
| Maintainer | [Release, monitor, back up and restore](docs/operations.md). |
| Developer | [DJI protocol](docs/protocol.md), [Blender contract](docs/blender.md) and [simulation procedure](docs/simulation.md). |

An **invitation code** registers one controller–aircraft pair. Registration supplies a **connection code** for later connections. Neither identifies the human pilot. The administrator does not need serial numbers in advance.

## Equipment and limits

Registration supports these pairs, subject to acceptance of the exact firmware and payload:

- Mavic 3 Enterprise with RC Pro Enterprise.
- Matrice 400 with RC Plus 2 Enterprise Enhanced.

This implements the Pilot 2 Cloud API MQTT/JSBridge interface. DJI's separate Cloud API 2 runtime is not included. See [compatibility and sources](docs/protocol.md#version-and-evidence-limits).

The connection sends telemetry only. It does not control the aircraft, upload photographs, create declarations or grant flight permission. **API accepted** needs a separate downstream reception check. Internet loss can leave gaps; expired samples are not replayed as live traffic. Details are in the [Blender contract](docs/blender.md).

## Developer checks

Requires Python 3.12+, uv, Node.js 22+ and Docker for integration tests.

```sh
uv sync --frozen
uv run ruff check src tests
uv run ruff format --check src tests
uv run pytest -q
node --test tests/portal.test.cjs
docker build -t dji-cloud-adaptor-app .
RUN_MQTT_INTEGRATION=1 RUN_STACK_INTEGRATION=1 uv run pytest -q
```

Tests use fictional devices and local receivers. Hosted simulation requires the [isolation procedure](docs/simulation.md#establish-isolation-before-a-real-write).
