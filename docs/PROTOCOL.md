# Pando cloud protocol

Derived from Android app v1.5-pando and observed traffic; implementation is independently written. Do not include APK/decompiled sources or account-specific captures in this repository.

- HTTPS host: `pando.iotpga.it`.
- `POST /users/login`: JSON `email`, `password`; response contains `JWT`.
- `GET /devices/`: bearer authentication, returns a device list with `uid`, `description`, `enable`, `properties`, `capabilities`. The integration does not use cached capability values as live state.
- `POST /devices/{uid}/set_value`: bearer authentication; command JSON below. Success bodies may be empty.
- MQTT TLS port 8883, MQTT 3.1.1. Username/password are the same account credentials, not the JWT. A unique random client ID avoids colliding with the phone app.
- Status: `root/pando/devices/{uid}/status`.
- Acknowledgement: `root/pando/devices/{uid}/response/{requestId}`. `status: 0` indicates success. Subscribe before sending HTTPS commands.

```json
{
  "command": "setValue",
  "requestId": "a fresh UUID",
  "parameters": [{"id": "device.lightOnOff", "value": 1}],
  "deviceType": "smartphone"
}
```

`getStatus` uses the same shape with an empty parameters list. There is no MQTT command publish in this app path: HTTPS dispatches it and MQTT carries responses.

```json
{
  "deviceId": "the device UID",
  "values": [{"id": "device.lightOnOff", "value": 1}],
  "timestamp": "device-reported timestamp"
}
```

State can be partial. Integer 0/1 is used for boolean capabilities. Command acknowledgement does not substitute for reported state. Device timestamps have no verified timezone/ordering guarantee and are not used as a freshness clock. Retained MQTT messages are ignored; a fresh status request must produce state.

Known writable controls: `device.onOff`, `device.fanSpeed`, `device.lightOnOff`, `device.lightBrightness`, `device.lightColorTemperature`, `device.cleanAirEnabled`. Bounds come from capability metadata. Power, flow and filter-time capabilities remain read-only. Filter remaining values are seconds; the Android widget divides by 3600 for hours.

The MQTT certificate observed on 12 October 2026 was expired. See README for exact pinning and verification details. No unconditional insecure-TLS mode exists in this client.
