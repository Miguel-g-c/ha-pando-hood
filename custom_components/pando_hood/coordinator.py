"""Push updates with periodic fresh-state checks."""

import logging
from datetime import timedelta

from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import AuthenticationError, PandoError
from .const import DOMAIN


class PandoCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry, cloud, hood):
        super().__init__(
            hass,
            logging.getLogger(__name__),
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=60),
        )
        self.cloud, self.hood = cloud, hood

    async def _async_update_data(self):
        try:
            return await self.cloud.refresh(self.hood.uid)
        except AuthenticationError as error:
            raise ConfigEntryAuthFailed(str(error)) from error
        except PandoError as error:
            raise UpdateFailed(str(error)) from error

    def state_received(self, uid):
        if uid == self.hood.uid:
            self.async_set_updated_data(dict(self.hood.values))

    def disconnected(self):
        if isinstance(self.cloud.failure, AuthenticationError):
            self.config_entry.async_start_reauth(self.hass)
        self.async_set_update_error(UpdateFailed("Pando MQTT disconnected"))

    async def set_values(self, values):
        try:
            await self.hood.set_values(self.cloud, values)
        except AuthenticationError as error:
            self.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError("Pando authentication expired") from error
        except (PandoError, ValueError) as error:
            raise HomeAssistantError(str(error)) from error
        # Command ACK is not state. Ask for fresh state; never replay setValue.
        await self.async_request_refresh()
