# Pando Hood for Home Assistant

Experimental custom integration for Pando Wi-Fi hoods, initially targeting the E297/120 V1130e BL with firmware v.2(1). Uses the same Pando cloud as the Android app. This version requires internet access; local Wi-Fi control has not been established.

## Entities

- Motor: off and four speeds. Motor-off preserves the light. Speed 4 follows the hood's own boost/timing behavior.
- Light: on/off, brightness and white temperature. The E297 reports 10–100% and 2700–6000 K.
- Switches: overall hood power and air-clean mode. Overall power is separate from motor-off and can affect the whole hood.
- Sensors: hood, motor and light power (W), reported airflow (m³/h), and remaining filter time (hours).
- Binary sensors: filter maintenance indicators.

Click **Motor** or **Light** on the device page to open speed, brightness and temperature controls. Motor speeds 1–4 correspond to 25%, 50%, 75% and 100%.

Entities appear only for capabilities the account reports. Filter 2 may be unused on a particular installation; disable its entities if appropriate. Airflow is the value reported by the hood; it has not been verified as a measured flow rate. Power values are instantaneous reports, not accumulated energy.

## Installation

The hood must already be enrolled and working in the Pando app. You need Home Assistant 2026.8.2 or later and internet access. No extra hardware, local lab or MQTT broker add-on is needed.

### HACS

1. Open **HACS → ⋮ → Custom repositories**.
2. Enter `https://github.com/Miguel-g-c/ha-pando-hood` and select **Integration**.
3. Find **Pando Hood**, download it and restart Home Assistant.
4. Follow the configuration steps below.

The repository is available through HACS custom repositories. Inclusion in the default catalog depends on HACS maintainer approval.

### Manual installation

1. Download the source archive from the [latest release](https://github.com/Miguel-g-c/ha-pando-hood/releases/latest).
2. Copy its `custom_components/pando_hood` folder into Home Assistant's `/config/custom_components/pando_hood`.
3. Restart Home Assistant.

### Configuration

1. Open **Settings → Devices & services → Add integration → Pando Hood**.
2. Enter the email and password used in Pando. The current MQTT server certificate is expired: review [Connection security](docs/SECURITY.md#setup-and-certificate-renewal) before deciding whether to fill in the optional certificate fingerprint field.
3. Select the hood. Its supported entities appear on the device page.

Tests have passed against Home Assistant 2026.8.2 and 2026.10.1; live installation has been verified on 2026.8.2 and 2026.10.4. The full release test suite runs against 2026.10.1.

## Behavior and limitations

Commands use verified HTTPS with bearer authentication. State and command acknowledgements use TLS MQTT. Subscriptions are established before commands; each acknowledgement is matched to its device and request ID. An HTTPS success alone does not indicate success. Acknowledgements also do not update entity state: the integration waits for reported state.

Partial state updates preserve unchanged fields. A fresh status request runs approximately every minute when there are no pushes. MQTT disconnection or a failed status refresh makes entities unavailable. Reconnection uses bounded exponential backoff; expired HTTP sessions renew once. Ambiguous command failures are surfaced and commands are never automatically repeated after timeout.

Light brightness below the device minimum is clamped; zero means off. Range checking uses device metadata and permits only the known control capabilities. No Wi-Fi enrollment, firmware flashing, account claiming or filter-reset commands are exposed.

This is an unofficial, reverse-engineered integration. Every exposed control (motor speeds, light on/off, brightness and white temperature, overall power, air-clean) and the sensors have been tested on a real E297/120 V1130e BL (firmware v.2(1)) through Home Assistant and work reliably.

## Development and live check

Development uses uv and Python 3.14.2 or later; `.python-version` selects the 3.14 series. Runtime dependencies and development tools are managed in `pyproject.toml` and pinned in `uv.lock`:

```sh
uv sync --locked
uv run pytest
uv run ty check
uv run ruff check .
uv run ruff format --check .
```

Run the read-only live check locally:

```sh
uv run python tools/live_check.py
```

Enter credentials at its terminal prompts, never into issue reports. The check requests fresh state; its certificate trust option is described in [Connection security](docs/SECURITY.md). By default it changes no controls. Add `--test-light` to briefly toggle and restore the light; keep other controls idle during that test. The private result goes to `/private/tmp/pando-app-private/cloud-live-check.json`; no credentials or tokens are saved. This diagnostic path is for the development Mac, not an HA dependency.

`client.py` contains the transport-neutral hood model and command interface. `cloud.py` implements HTTPS/MQTT. The test suite, Ruff checks and ty checks pass using the locked uv environment on Linux with Home Assistant 2026.10.1, including real HA setup, service control and unload against simulated network boundaries. The Mac's Python 3.14.7 crashed during interpreter cleanup after the full HA test, while the Linux run exited successfully; prefer Linux for the complete suite until that runtime issue is resolved.

Entities depend on the coordinator and model rather than cloud protocol details, so a future local transport can implement `Transport.command` and equivalent state/lifecycle behavior. A local endpoint must still be proven before such a transport can be implemented.

## Support and contributions

Open an [issue](https://github.com/Miguel-g-c/ha-pando-hood/issues) with your Home Assistant version, integration version, hood model/firmware, error text and redacted diagnostics. Never include account credentials, tokens or your full HA configuration. For unavailable entities, first confirm the hood still works in Pando and review [Connection security](docs/SECURITY.md).

Small fixes and tests are welcome. Run the development checks above before submitting a pull request. New device support should include sanitized capability examples and explain which controls were tested on hardware.
