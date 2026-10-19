# DJI Cloud API: protocol and design

[Home](../README.md) · [Deployment](deployment.md) · [Blender](blender.md)

Reviewed 19 October 2026. The relevant path is a **third-party cloud connection from Pilot 2**. This is not a REST API that lets us poll all DJI-owned cloud accounts. We host both the connection page and the MQTT service that the controller connects to.

## Onboarding handshake

1. The administrator issues a private one-use invitation without collecting serials. The operator chooses a supported aircraft model, and Pilot 2 supplies the controller/aircraft IDs; the server registers the pairing and returns its private connection code. Alternatively, the administrator pre-provisions a pair and issues its code. See [self-onboarding](self-onboarding.md).
2. The pilot opens our HTTPS address inside **Cloud Service → Open Platforms** in Pilot 2.
3. The page exchanges its connection code for a limited adapter session. Only authenticated sessions can retrieve our DJI application licence parameters.
4. The page calls `platformVerifyLicense(appId, appKey, license)` and checks the result.
5. It reads `platformGetRemoteControllerSN()` and asks the server to activate the session for that assigned controller. A mismatch revokes the session. Serial-number matching is a consistency check, not hardware attestation; the private code is the authentication secret.
6. It sets the workspace UUID and display information using `platformSetWorkspaceId` and `platformSetInformation`.
7. It loads the `api` module with our URL/session token and the `thing` module with MQTT host, username/password and a global connection callback.
8. Pilot 2 connects to the broker, sends topology and aircraft OSD. The page polls our private status endpoint and checks the native connection state.

The human pilot's identity is not inferred from the controller's connection code. Human identity, authorisation and flight planning remain in the organisation’s separate workflow.

The adapter's session token is stored hashed server-side. Pilot 2 may store it in its API module; we do not store it or the setup code in browser localStorage. The language preference alone uses localStorage, and the page still works when that storage is disabled. Sessions expire after 12 hours by default. Per-controller MQTT passwords remain valid until revoked/rotated; session expiry alone is not broker credential revocation.

## Topics

| Topic | Handling |
|---|---|
| `sys/product/{gateway_sn}/status` | Validate known controller and assigned sub-devices, store a secret-free topology summary, acknowledge `update_topo`. |
| `thing/product/{gateway_sn}/status` | Accepted as the documented per-device-page variant; reply still uses `sys/.../status_reply`. |
| `sys/product/{gateway_sn}/status_reply` | Receipt acknowledgement containing correlated `tid`, `bid`, current timestamp and result code. |
| `thing/product/{aircraft_sn}/osd` | Validate a complete current position and enqueue it. |
| Controller OSD/state | The broker accepts the controller's own publications, but they are not mapped as aircraft positions. |
| Aircraft state / partial OSD | State is not required for this position-only receiver. Partial OSD cannot inherit old coordinates. |
| Services, property writes, DRC | The adapter never publishes these. No configured broker role can publish aircraft commands. |

With self-onboarding enabled, Mosquitto dynamic-security provisions exact per-device grants and refreshes the worker role/subscriptions without restarting other connections. The separate server-side provisioner alone has broker-control access. Registration/invitation state and device secrets persist in the private SQLite volume; broker role state persists in the broker volume.

The worker subscribes to exact registered topics, not `#`. A controller can publish only its own status/OSD/state and its assigned aircraft's OSD/state. Pilot 2 can subscribe to its service inbox, but **no configured client can publish to it**. This accommodates the client's normal subscriptions without granting a control-command path.

The official topic overview and individual device page disagree on the status topic prefix; both input variants are explicitly supported and tested. We acknowledge only the topology method; we do not return successful receipts for arbitrary unsupported commands/features.

## Validation and delivery

- Source timestamps are milliseconds. Past/future limits are enforced on arrival; retained MQTT packets are rejected.
- Only registered aircraft topics with a matching gateway are used. A controller's GPS is not aircraft GPS.
- Latitude, longitude and `height` must be finite numbers in their expected ranges in the **same** OSD message. The common unset `(0,0)` pair is rejected.
- DJI `height` is ellipsoid height in metres. `elevation` is height relative to take-off and is retained separately in metadata; it is never substituted for `height`.
- Aircraft IDs sent to Blender are opaque hashes, not assigned ICAO addresses. Actual serial numbers remain in private configuration/database assignment fields, not normal logs.
- Incoming topology `device_secret`, nonce and arbitrary raw OSD data are not retained. Only an explicit telemetry-field allow-list is forwarded.
- A SQLite transaction commits before a received QoS1 message is acknowledged. QoS0 remains best effort; an outage between Pilot 2 and our broker can lose samples. A disk/queue failure is not acknowledged as durable receipt.
- Duplicate source samples are suppressed locally, including after restart. HTTP delivery is at least once: a lost HTTP response or process crash after server acceptance can still cause a duplicate at Blender. A stable `source_event_id` is supplied in metadata for downstream correlation; Blender-side idempotency is not assumed.
- Old pending samples expire from live delivery without changing their original timestamps. They remain inspectable privately until retention pruning.

Use one application process/worker and one configuration per SQLite database. Multiple organisations should initially have separate deployments, broker credentials, databases and Blender access. This implementation is not a shared multi-tenant authorisation service.

## Version and evidence limits

DJI's public documentation describes telemetry typically at 0.5 Hz. A server cannot recover positions never transmitted by an offline controller. No flight logging, media or mission-planning parity is claimed.

The older official `Cloud-API-Doc` GitHub snapshot reviewed at `4ec6b0c7f9472aeb09a0a47949855d19c473ea07` lacks newer model entries, while the hosted DJI product page lists M400. The shared envelope and height semantics were checked against the official Pilot property docs; M400 firmware, payload variants and actual packets still need device acceptance.

DJI also offers Cloud API 2 with a separate runtime and licence application process. This implementation neither bundles that platform nor claims licence interchangeability. We must verify the supplied application's Cloud API product selection on a real controller. The vendor demonstration server is a reference only, not a runtime dependency; no source from it is vendored here.

## Primary sources

- [Pilot 2 access to a third-party cloud](https://developer.dji.com/doc/cloud-api-tutorial/en/feature-set/pilot-feature-set/pilot-access-to-cloud.html)
- [JSBridge interfaces and return envelope](https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/pilot-to-cloud/jsbridge.html)
- [Official DJI bridge wrapper](https://github.com/dji-sdk/Cloud-API-Demo-Web/blob/main/src/api/pilot-bridge.ts), used to verify native return semantics.
- [Pilot MQTT topic definitions](https://github.com/dji-sdk/Cloud-API-Doc/blob/4ec6b0c7f9472aeb09a0a47949855d19c473ea07/docs/en/60.api-reference/10.pilot-to-cloud/00.mqtt/00.topic-definition.md)
- [Pilot aircraft property definitions, including height](https://github.com/dji-sdk/Cloud-API-Doc/blob/4ec6b0c7f9472aeb09a0a47949855d19c473ea07/docs/en/60.api-reference/10.pilot-to-cloud/00.mqtt/10.m3-series/00.properties.md)
- [Hosted DJI model/controller support](https://developer.dji.com/doc/cloud-api-tutorial/en/overview/product-support.html)
- [Cloud API 2](https://github.com/dji-sdk/Cloud-API-2)
- [Mosquitto authentication](https://mosquitto.org/documentation/authentication-methods/) and [configuration/ACL reference](https://mosquitto.org/man/mosquitto-conf-5.html)
