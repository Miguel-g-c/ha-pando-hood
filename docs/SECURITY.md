# Connection security

On 12 October 2026, `pando.iotpga.it:8883` presented a certificate expired since 5 March 2024. Its chain and hostname were independently verified with OpenSSL while excluding the date check. HTTPS authentication on port 443 uses normal certificate verification.

Default MQTT behavior requires normal CA, hostname and date validation, so this expired certificate prevents connection. The optional **MQTT certificate SHA-256 fingerprint** field enables an explicit exact-certificate trust decision. The observed leaf fingerprint was:

```
a73d5cf93adafc420f0d076b31564953a1d0d4433359f9e2e1a70828206ab2fc
```

Pinning verifies that exact certificate before sending MQTT credentials. It bypasses CA/hostname/date validation only for this MQTT connection and replaces them with exact certificate matching; it is restricted to the Pando hostname. It never accepts a changed certificate or learns replacement pins automatically. If Pando renews its certificate, reconfigure the entry: clear the pin to try normal validation, or independently verify a new pin. Never copy an unverified replacement from a connection error.

Account credentials are stored in Home Assistant's config entry, as required for MQTT reconnects. Keep your HA configuration and backups private. JWTs stay in memory. Diagnostics exclude credentials, account identifiers, hood identifiers and network properties.


The certificate fingerprint is a hash of the public server certificate, not a password or private key. Publishing it does not disclose a secret. Its authenticity and freshness still require independent verification.
