# Pando Hood for Home Assistant

Experimental custom integration for Pando Wi-Fi hoods, initially targeting the E297/120 V1130e BL with firmware v.2(1). Uses the same Pando cloud as the Android app. This version requires internet access; local Wi-Fi control has not been established.

## Entities

- Motor: off and four speeds. Motor-off preserves the light. Speed 4 follows the hood's own boost/timing behavior.
- Light: on/off, brightness and white temperature. The E297 reports 10–100% and 2700–6000 K.
- Switches: overall hood power and air-clean mode. Overall power is separate from motor-off and can affect the whole hood.
- Sensors: hood, motor and light power (W), reported airflow (m³/h), and remaining filter time (hours).
- Binary sensors: filter maintenance indicators.

Entities appear only for capabilities the account reports. Filter 2 may be unused on a particular installation; disable its entities if appropriate. Airflow is the value reported by the hood; it has not been verified as a measured flow rate. Power values are instantaneous reports, not accumulated energy.

## Installation

This repository has the custom-integration layout needed by HACS. A public GitHub repository/release is still needed before installation through HACS. Once published, add its URL as a HACS custom repository of category **Integration**, install Pando Hood and restart Home Assistant.

For the current development version:

1. Copy `custom_components/pando_hood` into Home Assistant's `/config/custom_components/pando_hood`.
2. Restart Home Assistant.
3. Open **Settings → Devices & services → Add integration → Pando Hood**.
4. Enter the email and password used in Pando, then select the hood.

Home Assistant 2025.2 or later is the declared minimum; automated tests currently run against 2026.10.1. Compatibility with the minimum version and installation on the real HA OS host are still pending.

### MQTT certificate issue

On 12 October 2026, `pando.iotpga.it:8883` presented a certificate expired since 5 March 2024. Its chain and hostname were independently verified with OpenSSL while excluding the date check. HTTPS authentication on port 443 uses normal certificate verification.

Default MQTT behavior requires normal CA, hostname and date validation, so this expired certificate prevents connection. The optional **MQTT certificate SHA-256 fingerprint** field enables an explicit exact-certificate trust decision. The observed leaf fingerprint was:

```
a73d5cf93adafc420f0d076b31564953a1d0d4433359f9e2e1a70828206ab2fc
```

Pinning verifies that exact certificate before sending MQTT credentials. It bypasses CA/hostname/date validation only for this MQTT connection and replaces them with exact certificate matching; it is restricted to the Pando hostname. It never accepts a changed certificate or learns replacement pins automatically. If Pando renews its certificate, reconfigure the entry: clear the pin to try normal validation, or independently verify a new pin. Never copy an unverified replacement from a connection error.

Account credentials are stored in Home Assistant's config entry, as required for MQTT reconnects. Keep your HA configuration and backups private. JWTs stay in memory. Diagnostics exclude credentials, account identifiers, hood identifiers and network properties.

## Behavior and limitations

Commands use verified HTTPS with bearer authentication. State and command acknowledgements use TLS MQTT. Subscriptions are established before commands; each acknowledgement is matched to its device and request ID. An HTTPS success alone does not indicate success. Acknowledgements also do not update entity state: the integration waits for reported state.

Partial state updates preserve unchanged fields. A fresh status request runs approximately every minute when there are no pushes. MQTT disconnection or a failed status refresh makes entities unavailable. Reconnection uses bounded exponential backoff; expired HTTP sessions renew once. Ambiguous command failures are surfaced and commands are never automatically repeated after timeout.

Light brightness below the device minimum is clamped; zero means off. Range checking uses device metadata and permits only the known control capabilities. No Wi-Fi enrollment, firmware flashing, account claiming or filter-reset commands are exposed.

This is an unofficial, reverse-engineered integration. Fresh state and light on/off plus restoration have been validated against the real hood. Fan, dimming, temperature and air-clean commands still need live validation before relying on automations.

## Development and live check

Use Python 3.14 for the current test environment:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
.venv/bin/ruff check custom_components tests tools
```

Run the read-only live check locally:

```sh
.venv/bin/python tools/live_check.py
```

Enter credentials at its terminal prompts, never into issue reports. The check offers an explicit pin of the above independently checked certificate, then requests fresh state. By default it changes no controls. Add `--test-light` to briefly toggle and restore the light; keep other controls idle during that test. The private result goes to `/private/tmp/pando-app-private/cloud-live-check.json`; no credentials or tokens are saved. This diagnostic path is for the development Mac, not an HA dependency.

`client.py` contains the transport-neutral hood model and command interface. `cloud.py` implements HTTPS/MQTT. All 16 tests and lint passed in Linux with Home Assistant 2026.10.1, including real HA setup, service control and unload against simulated network boundaries. The Mac's Python 3.14.7 crashed during interpreter cleanup after the full HA test, while the Linux run exited successfully; prefer Linux for the complete suite until that runtime issue is resolved.

Entities depend on the coordinator and model rather than cloud protocol details, so a future local transport can implement `Transport.command` and equivalent state/lifecycle behavior. A local endpoint must still be proven before such a transport can be implemented.

See the research documents for the local investigation and recovery procedures. No router DNS overrides or extra hardware are required for this cloud integration.

## Protocol and reference projects

Protocol findings came from this hood's Android app and captures, not from transplanting another brand's protocol. [LocalTuya](https://github.com/rospogrigio/localtuya) and [Philips air purifier](https://github.com/ruaan-deysel/ha-philips-airpurifier) demonstrate useful integration architecture, but their device-side local protocols do not establish one for Pando. Home Assistant's [config-flow](https://developers.home-assistant.io/docs/core/integration/config_flow/) and [data-coordinator](https://developers.home-assistant.io/docs/integration_fetching_data/) APIs govern setup and state handling.

Before publishing, point `manifest.json` documentation at this repository's README, set its verified GitHub code owner, and validate HACS metadata against the final repository.

## License

MIT. No APK, decompiled code, packet captures, private metadata, credentials or certificates are included in the distributable integration.
