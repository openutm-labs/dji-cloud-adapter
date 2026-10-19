# Immutable deployment, backup and rollback

[Deployment](deployment.md) · [Simulation](simulation.md) · [Acceptance](acceptance.md)

## Release package

Use a Docker-capable Linux VM with persistent disk, not request-only hosting. A small
2 GiB / 1 vCPU VM is a starting size for a supervised low-volume deployment; monitor
actual utilisation before scaling. For reference, [DigitalOcean's published Basic
pricing](https://www.digitalocean.com/pricing/droplets) listed 2 GiB, 1 vCPU and 50 GiB
disk at **US$12/month** on 19 October 2026, excluding domain, backups, taxes and overage.
Its [VM setup guide](https://docs.digitalocean.com/products/droplets/getting-started/recommended-droplet-setup/)
supports the required Linux host model. This is a recommendation, not a purchased host.

Provider account, host and domain allocation require the service owner's decision.
Existing unrelated cloud resources are not automatically available for this service.
No purchase, DNS change or public deployment is implied by a local container test.

From a clean, reviewed commit:

```sh
deploy/build-release.sh .integration-runtime/release-01
# For an x86 host when building on an ARM workstation with emulation configured:
# deploy/build-release.sh .integration-runtime/release-amd64 linux/amd64
```

The script archives only Git-tracked source, builds from that archive with an OCI
revision label, and saves `source.tar`, `image.tar` and `release.env` (commit, tag and
image ID and platform). The default platform is the Docker daemon's architecture;
match it to the selected host, or explicitly select `linux/amd64`/`linux/arm64` using
a builder with the required cross-build support. Never transfer an ARM-only image to
an x86 host. Inspect the commit's CI first. The base Python, Mosquitto and Caddy images
are digest-pinned; review and update their digests deliberately for patches. Runtime
dependencies have hashes in `requirements.lock`. Build tooling can evolve; the saved
image ID/digest is the immutable deployment artifact, not a promise of bit-identical
future rebuilds.

Transfer the source package and saved image to the chosen host; load with
`docker load -i image.tar`. Compare the loaded image ID with `release.env` and its
OCI revision with the full release commit. Copy private runtime through an approved
encrypted channel separately, never through Git or the image. Preserve its session
IDs, secrets and existing data. Do not run `init` over it. On Linux set private
directories 0700/files 0600 and set `ADAPTOR_UID/GID` for the dedicated service owner.
Set `ADAPTOR_RUNTIME` to the absolute runtime path in that host's private Compose env.

In the release source directory, export the saved commit-tagged `ADAPTOR_IMAGE` (or
prefer its registry `repository@sha256:...` after publishing the image):

```sh
export ADAPTOR_IMAGE=dji-cloud-adaptor:REPLACE_WITH_FULL_REVIEWED_COMMIT-amd64
docker compose --env-file /srv/dji/runtime/compose.env \
  -f compose.yml -f compose.production.yml -f compose.release.yml \
  config --quiet
docker compose --env-file /srv/dji/runtime/compose.env \
  -f compose.yml -f compose.production.yml -f compose.release.yml \
  up -d --no-build --wait --wait-timeout 90
```

Use the same Compose project name for every release of that deployment. It owns the
broker and Caddy named volumes. Never use `down -v` during upgrades or incident recovery.
Only Caddy exposes 80/443; use the host/provider firewall and restrict SSH. HTTPS/WSS
must use trusted public certificates on the selected DNS name. Test clients never
disable verification, and the private CA in local tests is not a production trust fix.

## Health and restart behaviour

The release overlay checks `/readyz` every 15 seconds; three failed checks mark the
app unhealthy. The normal process runs one worker, uses persistent SQLite WAL and
reconnects/retries its broker/API dependencies. Compose's `unless-stopped` restarts
exited containers and resumes them after a host reboot when Docker starts. Docker
does **not** automatically restart a merely unhealthy process.

Configure an external HTTPS monitor for `/readyz` (for example once a minute), and
host alerts for disk exhaustion, service health and failed backups. Assign an on-call
owner before normal operation. Investigate protected queue counts/age without putting
the admin token in command arguments or URLs. A healthy endpoint does not prove token
validity, telemetry delivery, downstream persistence or hardware licensing. Run the
read-only Blender check and bounded readback acceptance separately.

The local tests cover pending-outbox recovery, persistent duplicate suppression,
broker/app restarts, reconnection and device revocation. Real host reboot, DNS/public
certificates and external alert delivery must be checked on the chosen host.

## Consistent backup

Keep backups private/encrypted, outside the runtime directory, and record the full
release commit, image ID, runtime path and Compose project name. Back up app and broker
together; the broker's live dynamic-security file is authoritative after enrollment.

In the release directory, define `stack` with the same files/env/project as deployment:

```sh
stack() {
  docker compose --env-file /srv/dji/runtime/compose.env \
    -f compose.yml -f compose.production.yml -f compose.release.yml "$@"
}
umask 077
mkdir -p /srv/dji-backups/backup-01
stack stop
tar -C /srv/dji/runtime -cf /srv/dji-backups/backup-01/application.tar \
  config.json compose.env data broker
stack run --no-deps --rm --entrypoint sh \
  -v /srv/dji-backups/backup-01:/backup mqtt \
  -c 'tar -C /mosquitto/data -cf /backup/broker.tar .'
stack run --no-deps --rm --entrypoint sh \
  -v /srv/dji-backups/backup-01:/backup proxy \
  -c 'tar -C /data -cf /backup/caddy-data.tar .; tar -C /config -cf /backup/caddy-config.tar .'
stack start
```

Use a maintenance window and resume services even if a backup step fails. Separately
include any private handoff/invitation/recovery files held outside `data`. The stopped
app snapshot includes the database and WAL files; never copy only an active SQLite
main file. An online SQLite backup alone does not snapshot broker role changes.
Check archive integrity and encrypted off-host delivery before calling a backup good.

## Restore rehearsal

Restore into a new private runtime directory and **new Compose project**, isolated
from production ingress and Blender writes. Load the recorded image. Extract
`application.tar`, set the new runtime path/UIDs in its private env, and restore each
volume using `stack run --no-deps --rm --entrypoint sh` with the backup mounted read-only:
extract `broker.tar` under `/mosquitto/data`, `caddy-data.tar` under `/data`, and
`caddy-config.tar` under `/config`. Override `stack` to use the new env/project first.
Do not render old bootstrap JSON over the restored live dynamic-security file.

Check SQLite integrity, fleet/session/queue counts, broker authentication and revoked
device denial before allowing delivery. Pending samples beyond the live age must
expire rather than replay. Test HTTPS/WSS with the intended hostname, then repeat
bounded synthetic readback in an isolated context. Restore rehearsal of an actual
host backup remains required; local container restarts alone do not establish it.

## Rollback

Retain the previous source package, image and consistent backup. Stop the app, select
the previous immutable `ADAPTOR_IMAGE`, validate its config/database compatibility and
run `up -d --no-build --no-deps app` under the same project/runtime. This release adds
no database schema migration. Simulation config adds an aircraft `simulation` field
that older releases do not accept: keep such deployments stopped or restore the
compatible paired snapshot; do not strip simulation labels and forward their queue
as real traffic. Restoring an older paired snapshot can lose newer registrations and
revocations, so reconcile them before opening access. Preserve the failed state for
investigation and do not delete its volumes to make startup pass.
