from pathlib import Path

import pytest
from homeassistant import loader
from homeassistant.config_entries import ConfigEntries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.setup import async_setup_component
from test_transport import HTTP, Broker

from custom_components.pando_hood import cloud, config_flow


@pytest.mark.asyncio
async def test_ha_entry_creates_live_fan_and_service_updates_reported_state(tmp_path, monkeypatch):
    (tmp_path / "custom_components").symlink_to(
        Path(__file__).resolve().parents[1] / "custom_components"
    )
    hass = HomeAssistant(str(tmp_path))
    loader.async_setup(hass)
    hass.config_entries = ConfigEntries(hass, {})
    from homeassistant.bootstrap import async_load_base_functionality

    assert await async_load_base_functionality(hass)
    broker = Broker()
    http = HTTP(broker)
    monkeypatch.setattr(aiohttp_client, "async_get_clientsession", lambda h: http)
    monkeypatch.setattr(config_flow, "async_get_clientsession", lambda h: http)
    monkeypatch.setattr(cloud.aiomqtt, "Client", lambda *args, **kw: broker)
    try:
        assert await async_setup_component(hass, "pando_hood", {})
        result = await hass.config_entries.flow.async_init("pando_hood", context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "user", "password": "secret"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device_uid": "test"}
        )
        entry = result["result"]
        await hass.async_block_till_done()
        entities = hass.states.async_entity_ids("fan")
        assert len(entities) == 1
        assert hass.states.get(entities[0]).attributes["percentage"] == 50
        await hass.services.async_call("fan", "turn_off", {"entity_id": entities[0]}, blocking=True)
        await hass.async_block_till_done()
        assert hass.states.get(entities[0]).state == "off"
        transport = entry.runtime_data.cloud
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert not transport.ready.is_set()
    finally:
        await hass.async_stop(force=True)
