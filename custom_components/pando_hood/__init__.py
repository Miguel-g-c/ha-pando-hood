"""Pando hood custom integration."""

from .client import AuthenticationError, PandoError
from .cloud import Cloud
from .const import CONF_FINGERPRINT, CONF_UID, PLATFORMS


async def async_setup_entry(hass, entry):
    from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, EVENT_HOMEASSISTANT_STOP
    from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    from .coordinator import PandoCoordinator

    cloud = Cloud(
        async_get_clientsession(hass),
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        entry.data.get(CONF_FINGERPRINT, ""),
    )
    try:
        hoods = await cloud.devices()
        hood = next((h for h in hoods if h.uid == entry.data[CONF_UID]), None)
        if hood is None:
            raise ConfigEntryAuthFailed("Hood no longer belongs to this account")
        coordinator = PandoCoordinator(hass, entry, cloud, hood)
        await cloud.start([hood], coordinator.state_received, coordinator.disconnected)
        await coordinator.async_config_entry_first_refresh()
        entry.runtime_data = coordinator

        async def stop(event):
            await cloud.close()

        entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop))
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except AuthenticationError as error:
        await cloud.close()
        raise ConfigEntryAuthFailed(str(error)) from error
    except PandoError as error:
        await cloud.close()
        raise ConfigEntryNotReady(str(error)) from error
    except BaseException:
        await cloud.close()
        raise
    return True


async def async_unload_entry(hass, entry):
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.cloud.close()
        return True
    return False
