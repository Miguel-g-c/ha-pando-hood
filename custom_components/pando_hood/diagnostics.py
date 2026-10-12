"""Share useful diagnostics without account or network identifiers."""


async def async_get_config_entry_diagnostics(hass, entry):
    c = entry.runtime_data
    return {
        "transport": "cloud",
        "mqtt_connected": c.cloud.ready.is_set(),
        "certificate_pinning_enabled": bool(c.cloud.fingerprint),
        "last_update_success": c.last_update_success,
        "capabilities": sorted(c.hood.capabilities),
        "state": {k: v for k, v in (c.data or {}).items() if k in c.hood.capabilities},
    }
