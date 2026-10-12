from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from test_cloud import HTTP, Reply

from custom_components.pando_hood import config_flow
from custom_components.pando_hood.const import CONF_FINGERPRINT


async def test_flow_rejects_wrong_credentials_then_creates_selected_hood_entry(
    tmp_path, monkeypatch
):
    # Exercise Home Assistant's actual flow manager, not a handcrafted flow instance.
    from pathlib import Path

    (tmp_path / "custom_components").symlink_to(
        Path(__file__).resolve().parents[1] / "custom_components"
    )
    hass = HomeAssistant(str(tmp_path))
    from homeassistant import loader

    loader.async_setup(hass)
    from homeassistant.config_entries import ConfigEntries

    hass.config_entries = ConfigEntries(hass, {})
    await hass.config_entries.async_initialize()
    try:
        assert await async_setup_component(hass, "pando_hood", {})
        http = HTTP(
            [
                Reply(401, {}),
                Reply(200, {"JWT": "token"}),
                Reply(200, [{"uid": "test", "description": "Kitchen", "capabilities": []}]),
            ]
        )
        monkeypatch.setattr(config_flow, "async_get_clientsession", lambda h: http)
        result = await hass.config_entries.flow.async_init("pando_hood", context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "user", "password": "wrong"}
        )
        assert result["errors"] == {"base": "invalid_auth"}
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "user", "password": "correct", CONF_FINGERPRINT: "a" * 64},
        )
        assert result["step_id"] == "device"
        # Prevent background entry setup: this test concerns the actual configuration flow.
        monkeypatch.setattr(hass.config_entries, "async_setup", no_setup)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device_uid": "test"}
        )
        assert result["type"] == "create_entry"
        assert result["result"].unique_id == "test"
        entry = result["result"]
        monkeypatch.setattr(hass.config_entries, "async_reload", no_setup)
        for source, fingerprint in (
            ("reauth", "a" * 64),
            ("reconfigure", "a" * 64),
            ("reconfigure", ""),
        ):
            http = HTTP(
                [
                    Reply(200, {"JWT": "token"}),
                    Reply(200, [{"uid": "test", "description": "Kitchen", "capabilities": []}]),
                ]
            )
            result = await hass.config_entries.flow.async_init(
                "pando_hood",
                context={"source": source, "entry_id": entry.entry_id},
                data=dict(entry.data) if source == "reauth" else None,
            )
            # Match the frontend's default-filled form submission when the user
            # updates credentials without changing the optional certificate field.
            schema = result["data_schema"]
            assert schema is not None
            inputs = schema({"username": "user", "password": "updated"})
            if not fingerprint:
                inputs[CONF_FINGERPRINT] = ""
            result = await hass.config_entries.flow.async_configure(result["flow_id"], inputs)
            assert result["type"] == "abort"
            assert entry.data["password"] == "updated"
            assert entry.data[CONF_FINGERPRINT] == fingerprint

    finally:
        await hass.async_stop(force=True)


async def no_setup(*args, **kwargs):
    return True
