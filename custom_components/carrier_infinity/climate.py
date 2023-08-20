"""Platform for climate integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import HVACMode
from homeassistant.const import TEMP_FAHRENHEIT
from homeassistant.core import HomeAssistant
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
    for (system_id, system) in systems.items():
        coordinator = MyCoordinator(hass, system)
        coordinators.append(coordinator)
        config = await system.get_config()
        for zone_id in config.zones:
            zones.append(Zone(coordinator, zone_id))

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
    def __init__(self, coordinator, zone_id):
        super().__init__(coordinator)
        self.zone_id = zone_id

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


