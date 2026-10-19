# Flight Blender integration contract

[Home](../README.md) · [Protocol](protocol.md) · [Acceptance](acceptance.md)

## First-version endpoint

`POST /flight_stream/set_air_traffic/{session_id}` with `Authorization: Bearer ...` and an `observations` array. Verify this contract against your deployment’s OpenAPI document at `<BLENDER_BASE_URL>/openapi.json`.

The adapter generates a stable UUID traffic session per configured aircraft. It is not an automatically created or approved operation. We do not call declaration, approval or DSS-submission endpoints.

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

The project's resolved API reference defines `traffic_source=11` as Network Remote-ID and `source_type=0` as direct/true rather than fused data. These are configurable defaults, **not an assertion that DJI Cloud telemetry fulfils an ASTM RID service**. Confirm the desired classification and display handling with the Blender team before deployment.

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
4. Whether operations need binding to declarations. If so, agree a pilot/aircraft/operation mapping and implement a separate authorised workflow; do not equate a generated traffic UUID to regulatory approval.
5. Historical data ingestion requirements, if any. This version intentionally does not import old flight logs into a live feed.

No production declaration, telemetry or account was submitted as part of local automated testing.
