# Deployment acceptance

[Home](../README.md) · [Deployment](deployment.md) · [Protocol](protocol.md)

Use this procedure for each deployment and equipment combination. Automated tests and browser previews do not establish actual-controller compatibility or downstream data reception. Record results, dates, versions and owners in your organization's operations documentation.

## Required before deployment

- [ ] Select a reviewed release and inspect its CI results.
- [ ] Assign hosting, DNS, persistent storage, monitoring and backup owners.
- [ ] Configure the correct DJI Cloud API application and Blender credentials.
- [ ] Agree traffic classification, data handling and separate pilot/declaration procedures.
- [ ] Verify OAuth token acquisition and protected access with TLS verification enabled.

The [read-only access check](blender.md#check-access-without-submitting-traffic) does not submit telemetry. Use the [isolation procedure](simulation.md#establish-isolation-before-a-real-write) before synthetic writes to a hosted target.

## Required on each real equipment combination

Use the organization's approved ground procedure. Do not start motors or take off solely for connection setup.

1. Open the HTTPS address through **Pilot 2 → Cloud Service → Open Platforms**.
2. Verify certificate trust, layout and DJI application licensing on the actual controller.
3. Register the correct controller–aircraft pair and verify the MQTT WebSocket connection.
4. Examine a current aircraft position, equipment identity, height reference, units and source timestamp.
5. Verify Blender API acceptance and independently examine downstream reception and display.
6. Reopen the page and reconnect with the same equipment's saved connection code.
7. Check approved ground connectivity interruptions, stale indicators and reconnection.
8. Verify app/broker restarts and controller revocation. Old data must not return as current traffic.
9. Make sure that Pilot 2 retains aircraft control and the adapter never requests cloud flight-control authority.

A green status or HTTP response alone does not prove storage of a full track. Complete the organization's operational acceptance and reporting process before wider use.

## Optional declaration workflow

Complete these checks only when declarations are enabled. Use an isolated Blender environment for synthetic declarations and the approved procedure for any real flight.

1. Confirm the operator, controller-specific pilot roster, planning limits, altitude margin and source-clock accuracy bound. Verify the API contracts in the [Blender guide](blender.md#optional-pilot-declarations).
2. On the actual controller, review a ground plan and compare coordinates, WGS84 altitude range and local/UTC times with the intended flight volume.
3. Submit once. Independently verify the declaration’s aircraft, submitting pilot, operator and volume in Blender. Confirm that unapproved and out-of-window activation are refused.
4. Exercise a lost submission response and page reopen in isolation. Recover the same declaration without a second creation POST. Check controller and roster isolation.
5. Activate through the accepted workflow and verify operation-linked telemetry downstream. General traffic API acceptance must not count as declaration telemetry acceptance.
6. Exercise accepted ground interruptions and an adapter restart. Original timestamps and declaration association must survive. Expired or rejected observations must show as gaps.
7. After landing, end the declaration, drain its queue and verify the final Blender state. Check the next flight receives a distinct declaration and no previous samples.

## Recovery and records

Use the [operations guide](operations.md) to verify host reboot, alerts, consistent app/broker backups and restoration. Keep credentials, serial inventories, flight records and acceptance reports outside this repository.

Generic developer checks are in the [README](../README.md#developer-checks). The [simulator](simulation.md) checks software contracts; it does not emulate native Pilot 2 licensing or establish flight readiness.
