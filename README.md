# Pando Hood for Home Assistant

Unofficial integration for Pando Wi-Fi hoods. It talks to the same Pando cloud as the Pando Android / iOS app, so it needs internet access. Local control is not supported yet.

Tested on a real E297/120 V1130e BL with firmware v.2(1). All controls and sensors below work on that hood. Other models may work, but they are not tested.

## Requirements

- Home Assistant 2026.8.2 or later.
- The hood is already set up and working in the Pando app.

No extra hardware or MQTT broker is needed.

## Installation

### HACS

1. Open **HACS** and search for **Pando Hood**.
2. Download it and restart Home Assistant.

### Manual

1. Download the [latest release](https://github.com/Miguel-g-c/ha-pando-hood/releases/latest).
2. Copy `custom_components/pando_hood` into `/config/custom_components/pando_hood`.
3. Restart Home Assistant.

## Configuration

1. Go to **Settings → Devices & services → Add integration → Pando Hood**.
2. Enter your Pando email and password.
3. Select your hood.

The optional certificate fingerprint field exists because the Pando MQTT server certificate is currently expired. Read [Connection security](docs/SECURITY.md#setup-and-certificate-renewal) before you fill it in.

## Entities

| Entity | What it does |
| --- | --- |
| Motor | Off and speeds 1 to 4 (25%, 50%, 75%, 100%). Turning the motor off keeps the light on. Speed 4 follows the hood's own boost timer. |
| Light | On/off, brightness (10 to 100%) and white temperature (2700 to 6000 K). |
| Hood power | Turns the whole hood on or off. This is not the same as motor off. |
| Air clean | Turns air-clean mode on or off. |
| Power sensors | Hood, motor and light power in W. These are live values, not energy totals. |
| Airflow | Airflow in m³/h as reported by the hood. It is not a measured value. |
| Filter | Remaining filter time in hours, plus filter maintenance indicators. |

Open **Motor** or **Light** on the device page to change speed, brightness or temperature.

You only get entities for features your hood reports. If you don't use filter 2, you can disable its entities.

## How it works

- Commands go over HTTPS. State updates and command confirmations come over TLS MQTT.
- An entity changes only when the hood reports the new state, not when the command is sent.
- If no update arrives for about 1 minute, the integration asks the hood for its state.
- If MQTT disconnects or a state request fails, the entities become unavailable until it reconnects.
- A command that times out is reported as an error. It is never sent again automatically.
- Brightness below the hood minimum is set to the minimum. Brightness 0 turns the light off.

The integration does not do Wi-Fi setup, firmware updates, account linking or filter resets.

## Support

Open an [issue](https://github.com/Miguel-g-c/ha-pando-hood/issues) and include:

- Home Assistant version and integration version
- Hood model and firmware
- The error text and redacted diagnostics

Never share your Pando password, tokens or full HA configuration. If entities are unavailable, first check that the hood still works in the Pando app, then read [Connection security](docs/SECURITY.md).

## Development

You need uv and Python 3.14.2 or later.

```sh
uv sync --locked
uv run pytest
uv run ty check
uv run ruff check .
uv run ruff format --check .
```

Run the full test suite on Linux. On macOS, Python 3.14.7 crashes during cleanup after the full HA test run.

To check a real hood without changing anything:

```sh
uv run python tools/live_check.py
```

It asks for your credentials in the terminal and saves no credentials or tokens. The result goes to `/private/tmp/pando-app-private/cloud-live-check.json`. Add `--test-light` to turn the light on and off once and then restore it. Don't use other controls during that test.

Code layout:

- `client.py`: the hood model and command interface. It does not depend on the transport.
- `cloud.py`: the HTTPS and MQTT transport.

Entities use the model, not the cloud protocol. So a local transport can be added later by implementing `Transport.command`, once a local endpoint is found.

Pull requests are welcome. Run the checks above first. For a new hood model, add sanitized capability examples and say which controls you tested on real hardware.
