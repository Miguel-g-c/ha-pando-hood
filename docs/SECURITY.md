# Connection security

On 12 October 2026, `pando.iotpga.it:8883` presented a certificate expired since 5 March 2024. Its chain and hostname were independently verified with OpenSSL while excluding the date check. HTTPS authentication on port 443 uses normal certificate verification.

Default MQTT behavior requires normal CA, hostname and date validation, so this expired certificate prevents connection. The optional **MQTT certificate SHA-256 fingerprint** field enables an explicit exact-certificate trust decision. The observed leaf fingerprint was:

```
a73d5cf93adafc420f0d076b31564953a1d0d4433359f9e2e1a70828206ab2fc
```

Pinning verifies that exact certificate before sending MQTT credentials. It bypasses CA/hostname/date validation only for this MQTT connection and replaces them with exact certificate matching; it is restricted to the Pando hostname. It never accepts a changed certificate or learns replacement pins automatically. If Pando renews its certificate, reconfigure the entry: clear the pin to try normal validation, or independently verify a new pin. Never copy an unverified replacement from a connection error.

Account credentials are stored in Home Assistant's config entry, as required for MQTT reconnects. Keep your HA configuration and backups private. JWTs stay in memory. Diagnostics exclude credentials, account identifiers, hood identifiers and network properties.


The certificate fingerprint is a hash of the public server certificate, not a password or private key. Publishing it does not disclose a secret. Its authenticity and freshness still require independent verification.

## Setup and certificate renewal

1. Try leaving **MQTT certificate SHA-256 fingerprint** blank for normal certificate verification.
2. If setup fails because of the expired MQTT certificate, read the trust trade-off above. If you accept trusting the exact certificate verified on 12 October 2026, enter its fingerprint from this document when adding the integration. This is an explicit trust decision; the integration never enables it automatically.
3. To change an existing entry, open **Settings → Devices & services → Pando Hood → ⋮ → Reconfigure**. Enter your account credentials and either clear the fingerprint to restore normal verification or supply an independently verified replacement.
4. If a stored pin stops matching, first try clearing it: Pando may have renewed its certificate. Never adopt a new fingerprint merely because it appears in a connection error.

Report a suspected credential leak through [GitHub private vulnerability reporting](https://github.com/Miguel-g-c/ha-pando-hood/security/advisories/new). Do not post secrets in public issues.
