# Connect your DJI controller to OpenUTM

[Español](pilot-es.md) · [Project home](../README.md)

**This connection is awaiting real-controller acceptance and hosting.** Your coordinator must confirm it is ready before issuing the final link. A website preview alone does not connect an aircraft.

## Before you begin

You need:

- The lab's approved aircraft and controller running **DJI Pilot 2**. Panama's first targets are Mavic 3 Enterprise and Matrice 400 with their correct controllers.
- Working internet on the controller.
- The **controller connection website address** from your coordinator.
- A private **connection code assigned to this controller**.

You do not need an APK, developer account or command-line tool for this route. Your connection code is not your Passport password and does not identify the human pilot. Continue the lab's normal pilot sign-in, planning and permission steps separately.

## 1. Open the connection page

1. Follow the lab's normal ground setup with the aircraft safely on the ground.
2. Open DJI Pilot 2.
3. On its home page, open **Cloud Service → Open Platforms**. Labels can vary by Pilot version; ask your coordinator if the menu differs.
4. Enter the exact HTTPS website address supplied for your lab.
5. Check the lab's expected website address and that there is no certificate warning. If the address or certificate is wrong, stop and ask the coordinator.
6. Choose **English** or **Español** at the top of the page.

If the page says **Open this page in DJI Pilot 2**, it is running in a regular browser. Return to Pilot 2 and open it from **Open Platforms**.

## 2. Enter your controller's code

1. Enter the private code in **Connection code**.
2. Tap **Connect telemetry →**.
3. Wait while Pilot 2 verifies the application licence and connects.

Do not share the code or take a screenshot with it visible. If the page says the code belongs to another controller, ask for the correct code; do not select another pilot or aircraft to work around it.

## 3. Check the three statuses

| Status | What to check |
|---|---|
| **Controller connection** | **Connected** means Pilot 2 reports a connection to the telemetry broker. |
| **Aircraft telemetry** | **Connected** means the adapter has received a recent position from a registered aircraft. |
| **Flight Blender** | **API accepted** means Blender's API accepted a recent sample. The lab must also verify its downstream record/dashboard. |

Check **Last aircraft sample**, **Last API acceptance** and **Waiting to send**. **Not configured**, **Not recent**, **Waiting** or **Status unavailable** need review; they do not mean everything is ready.

You do not need to take off or start motors to test connection. A usable aircraft position may depend on the normal ground setup and GPS reception. Follow the coordinator's ground-check instructions.

## 4. Continue the lab's normal operating procedure

This connection shares telemetry only. It does not create a flight declaration, approve a flight, choose a pilot or upload photographs. Your coordinator must explain the separate planning, identity and permission workflow before an operation.

Pilot 2 remains the flight application. This adapter does not ask for remote control, and the page must not ask you to enable cloud flight-control authority. Resolve any unexpected prompt with the coordinator.

Keep the controller connected to internet when the lab requires live tracking. Internet loss can interrupt the transmitted track; this service does not guarantee later recovery of positions the controller never sent.

## If something goes wrong

| Problem | What to do |
|---|---|
| No Open Platforms option | Confirm the exact controller, Pilot 2 version and approved combination with the coordinator. |
| Application licence cannot be verified | Ask the coordinator to check the DJI application setup and controller version. Reinstalling an APK is not part of this connection. |
| Invalid code or wrong controller | Check the complete assigned code; request a corrected one if necessary. |
| Too many attempts | Wait one minute, then retry. Ask the coordinator if unsure which code to use. |
| Controller connects but aircraft telemetry waits | Check aircraft power/link, registered pairing and normal GPS setup while on the ground. |
| Blender is not configured or sending remains pending | Ask the coordinator to check the server's API credentials/service status. Do not change aircraft dates or recreate operations to fix this. |
| Session ended | Enter the controller's code again. This is separate from your Passport account. |
| Internet or status disappears | Treat live tracking as interrupted and follow the lab's procedure. Do not change flight-control apps during a flight. |

Report the failed step, exact message, controller/aircraft models, Pilot version and time/time zone through the lab's approved private support channel. Never send your connection code, passwords or setup credentials.

To end this cloud connection while safely on the ground, use **Disconnect this controller**. For a lost/shared controller, ask the coordinator to handle access revocation; closing a browser page alone does not revoke its MQTT credentials.
