"""Shared entity metadata and reported-state access."""

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class PandoEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, key, name):
        super().__init__(coordinator)
        self.key = key
        self._attr_name = name
        hood = coordinator.hood
        self._attr_unique_id = f"{hood.uid}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, hood.uid)}, manufacturer="Pando", name=hood.name
        )

    @property
    def available(self):
        return super().available and self.key in (self.coordinator.data or {})

    @property
    def value(self):
        return (self.coordinator.data or {}).get(self.key)
