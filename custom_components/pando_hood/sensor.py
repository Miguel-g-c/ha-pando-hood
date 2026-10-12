"""Reported power, flow and remaining filter time."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass

from .entity import PandoEntity

SENSORS = (
    ("device.hoodPower", "Power", "W", SensorDeviceClass.POWER, 1),
    ("device.fanPower", "Motor power", "W", SensorDeviceClass.POWER, 1),
    ("device.lightPower", "Light power", "W", SensorDeviceClass.POWER, 1),
    ("device.fanFlow", "Airflow", "m³/h", None, 1),
    ("device.filter1Value", "Filter 1 remaining", "h", SensorDeviceClass.DURATION, 3600),
    ("device.filter2Value", "Filter 2 remaining", "h", SensorDeviceClass.DURATION, 3600),
)


async def async_setup_entry(hass, entry, async_add_entities):
    c = entry.runtime_data
    async_add_entities(
        [PandoSensor(c, *spec) for spec in SENSORS if spec[0] in c.hood.capabilities]
    )


class PandoSensor(PandoEntity, SensorEntity):
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, key, name, unit, device_class, divisor):
        super().__init__(coordinator, key, name)
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self.divisor = divisor
        self._attr_suggested_display_precision = 1 if divisor == 3600 else 0

    @property
    # HA exposes this as a writable cached_property; live state needs a property.
    def native_value(self):  # ty: ignore[invalid-property-type-override]
        return self.value / self.divisor if self.value is not None else None
