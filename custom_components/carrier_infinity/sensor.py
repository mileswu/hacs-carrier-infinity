from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN
from python_carrier_infinity.types import TemperatureUnits

async def async_setup_entry(hass, entry, async_add_entities) -> None:
    systems_and_coordinators = hass.data[DOMAIN][entry.entry_id]

    sensors = []
    for (system, coordinator) in systems_and_coordinators:
        sensors.append(OutsideTemperature(coordinator, system))
        sensors.append(Airflow(coordinator, system))

    async_add_entities(sensors)

class OutsideTemperature(CoordinatorEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
    _attr_has_entity_name = True
    _attr_name = "Outside Temperature"

    def __init__(self, coordinator, system):
        super().__init__(coordinator)
        self._attr_unique_id = f"{system.serial}-outsidetemp"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, system.serial)},
            name=system.name,
            manufacturer="Carrier",
            model="Infinity System"
        )

    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data

        if data.status.temperature_units == TemperatureUnits.CELCIUS:
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        elif data.status.temperature_units == TemperatureUnits.FARENHEIT:
            self._attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
        else:
            raise ValueError("TemperatureUnits not handled", data.status.temperature_units)

        self._attr_native_value = data.status.outside_temperature
        self.async_write_ha_state()

class Airflow(CoordinatorEntity, SensorEntity):
    _attr_device_class = None
    _attr_native_unit_of_measurement = "cfm"
    _attr_has_entity_name = True
    _attr_name = "Airflow"

    def __init__(self, coordinator, system):
        super().__init__(coordinator)
        self._attr_unique_id = f"{system.serial}-airflow"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, system.serial)},
            name=system.name,
            manufacturer="Carrier",
            model="Infinity System"
        )

    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data
        self._attr_native_value = data.status.airflow
        self.async_write_ha_state()
