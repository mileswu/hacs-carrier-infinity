"""Platform for climate integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import HVACMode
from homeassistant.const import TEMP_FAHRENHEIT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
# from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

import python_carrier_infinity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities) -> None:
    auth = hass.data[DOMAIN][entry.entry_id]

    systems = await python_carrier_infinity.get_systems(auth)
    zones = []
    coordinators = []
    for system in systems.values():
        coordinator = MyCoordinator(hass, system)
        coordinators.append(coordinator)
        config = await system.get_config()
        for zone_config in config.zones.values():
            zones.append(Zone(coordinator, system, zone_config))

    async_add_entities(zones)
    for coordinator in coordinators:
        await coordinator.async_config_entry_first_refresh()

class MyCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, system):
        super().__init__(
            hass,
            _LOGGER,
            name=system.name,
            update_interval=timedelta(seconds=60),
        )
        self.system = system

    async def _async_update_data(self):
        config = await self.system.get_config()
        status = await self.system.get_status()
        return CoordinatorUpdate(self.system, config, status)

class CoordinatorUpdate():
    def __init__(self, system, config, status):
        self.system = system
        self.config = config
        self.status = status

class Zone(CoordinatorEntity, ClimateEntity):
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, coordinator, system, zone_config):
        super().__init__(coordinator)
        self.zone_id = zone_config.id
        self._attr_unique_id = f"{system.serial}-{zone_config.id}"
        name = f"{system.name} - {zone_config.name}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name=name,
            manafacturer="Carrier",
            model="Infinity System"
        )

    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data
        self._attr_current_temperature = data.status.zones[self.zone_id].temperature
        self.async_write_ha_state()

    @property
    def hvac_modes(self):
        return []

    @property
    def supported_features(self):
        return 0

    @property
    def temperature_unit(self) -> str:
        return TEMP_FAHRENHEIT

    @property
    def hvac_mode(self) -> HVACMode | None:
        return None
