"""Set up one hood with Pando account credentials."""

import re

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import AuthenticationError, PandoError
from .cloud import Cloud
from .const import CONF_FINGERPRINT, CONF_UID, DOMAIN


class PandoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        return await self._credentials("user", user_input)

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        return await self._credentials("reauth_confirm", user_input)

    async def async_step_reconfigure(self, user_input=None):
        return await self._credentials("reconfigure", user_input)

    async def _credentials(self, step, user_input):
        errors = {}
        if user_input is not None:
            pin = user_input.get(CONF_FINGERPRINT, "").replace(":", "").strip().lower()
            if pin and not re.fullmatch("[0-9a-f]{64}", pin):
                errors[CONF_FINGERPRINT] = "invalid_fingerprint"
            else:
                user_input = {
                    **user_input,
                    CONF_USERNAME: user_input[CONF_USERNAME].strip(),
                    CONF_FINGERPRINT: pin,
                }
                cloud = Cloud(
                    async_get_clientsession(self.hass),
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                    pin,
                )
                try:
                    self.hoods = await cloud.devices()
                except AuthenticationError:
                    errors["base"] = "invalid_auth"
                except PandoError:
                    errors["base"] = "cannot_connect"
                else:
                    if step != "user":
                        entry = (
                            self._get_reauth_entry()
                            if step == "reauth_confirm"
                            else self._get_reconfigure_entry()
                        )
                        if entry.data[CONF_UID] not in {h.uid for h in self.hoods}:
                            errors["base"] = "device_not_found"
                        else:
                            return self.async_update_reload_and_abort(
                                entry, data_updates=user_input
                            )
                    elif not self.hoods:
                        return self.async_abort(reason="no_devices")
                    else:
                        self.credentials = user_input
                        return await self.async_step_device()
        return self.async_show_form(
            step_id=step,
            # HA accepts legacy voluptuous schemas at runtime for older Core support.
            data_schema=vol.Schema(  # ty: ignore[invalid-argument-type]
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(CONF_FINGERPRINT, default=""): str,
                }
            ),
            errors=errors,
        )

    async def async_step_device(self, user_input=None):
        if user_input is not None:
            uid = user_input[CONF_UID]
            await self.async_set_unique_id(uid)
            self._abort_if_unique_id_configured()
            hood = next(h for h in self.hoods if h.uid == uid)
            return self.async_create_entry(
                title=hood.name, data={**self.credentials, CONF_UID: uid}
            )
        return self.async_show_form(
            step_id="device",
            # HA accepts legacy voluptuous schemas at runtime for older Core support.
            data_schema=vol.Schema(  # ty: ignore[invalid-argument-type]
                {vol.Required(CONF_UID): vol.In({h.uid: f"{h.name} ({h.uid})" for h in self.hoods})}
            ),
        )
