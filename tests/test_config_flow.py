from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from test_cloud import HTTP, Reply

from custom_components.pando_hood import config_flow


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
            result["flow_id"], {"username": "user", "password": "correct"}
        )
        assert result["step_id"] == "device"
        # Prevent background entry setup: this test concerns the actual configuration flow.
        monkeypatch.setattr(hass.config_entries, "async_setup", no_setup)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device_uid": "test"}
        )
        assert result["type"] == "create_entry"
        assert result["result"].unique_id == "test"
    finally:
        await hass.async_stop(force=True)


async def no_setup(*args, **kwargs):
    return True
