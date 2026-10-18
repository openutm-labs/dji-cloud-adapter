# Flight Blender integration contract

[Home](../README.md) · [Protocol](protocol.md) · [Acceptance](acceptance.md)

## First-version endpoint

`POST /flight_stream/set_air_traffic/{session_id}` with `Authorization: Bearer ...` and an `observations` array. This route is present in the [Panama hosted OpenAPI document](https://blender.panama.openutm.net/openapi.json).

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
| Adapter metadata | `metadata` | Source, lab UUID, aircraft alias/model, altitude reference, source event ID, no asserted RID compliance. |

The project's resolved API reference defines `traffic_source=11` as Network Remote-ID and `source_type=0` as direct/true rather than fused data. These are configurable defaults, **not an assertion that DJI Cloud telemetry fulfils an ASTM RID service**. Confirm the desired classification and display handling with the Blender team before Panama rollout.

## Authentication

The hosted OpenAPI specification declares HTTP bearer security but does not document a token endpoint, audience, scopes or provisioning flow. Obtain those from the hosting team. The reviewed Blender source uses `flightblender.write` for this endpoint; hosted settings must still be confirmed.

### Panama server configuration

The programme owner supplied the following authentication flow on 19 October 2026. It was checked from the local adaptor with normal TLS verification:

| Setting | Panama value |
|---|---|
| Blender base URL | `https://blender.panama.openutm.net` |
| Token URL | `https://auth.panama.openutm.net/oauth/token/` |
| Grant / client authentication | `client_credentials` / credentials in the form body |
| Audience | `blender.panama.openutm.net` — hostname only, not a Markdown link or an HTTP URL |
| Requested scope | `flightblender.read flightblender.write` |
| Client ID and secret | Private runtime configuration only; obtain through the authorised service owner. |

Token issuance, cache reuse, forced renewal and a protected read were verified. The protected surveillance-health GET returned 401 without a token and 200 with it. No token or response body is retained in the public evidence. No aircraft observation or declaration was submitted; write-path acceptance and downstream persistence still need a supervised real-device check. The supplied credentials have been configured only in the local ignored runtime, not in a hosted service or image.

Do not use `curl -k` or disable certificate verification. Both Panama endpoints passed normal HTTPS verification during this check. Never put the client secret in a command argument, shared shell history, pilot setup file or documentation.

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

1. Continued validity/ownership of Panama's supplied OAuth client and its permissions; verify actual traffic writes during supervised acceptance. Token issuance and protected reads have been checked locally.
2. Traffic-source classification, height datum/units, source timestamp interpretation and opaque aircraft identifier handling.
3. That asynchronous ingestion workers and the intended Spotlight/other display consume this traffic feed correctly.
4. Whether operations need binding to declarations. If so, agree a pilot/aircraft/operation mapping and implement a separate authorised workflow; do not equate a generated traffic UUID to regulatory approval.
5. Historical data ingestion requirements, if any. This version intentionally does not import old flight logs into a live feed.

No production declaration, telemetry or account was submitted as part of local automated testing.
