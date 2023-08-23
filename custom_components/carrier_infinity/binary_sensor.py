from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities) -> None:
    systems_and_coordinators = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for (system, coordinator) in systems_and_coordinators:
        entities.append(HumidifierActive(coordinator, system))

    async_add_entities(entities)

class HumidifierActive(CoordinatorEntity, BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Humidifier"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator, system):
        super().__init__(coordinator)
        self._attr_unique_id = f"{system.serial}-humidifieractive"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, system.serial)},
            name=system.name,
            manufacturer="Carrier",
            model="Infinity System"
        )

    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data
        self._attr_is_on = data.status.humidifier_active
        self.async_write_ha_state()
