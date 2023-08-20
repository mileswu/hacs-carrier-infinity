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
    coordinator = MyCoordinator(hass, auth)

    systems = await python_carrier_infinity.get_systems(auth)
    zones = []
    for (system_id, system) in systems.items():
        config = await system.get_config()
        for (zone_id, zone) in config.zones.items():
            zones.append(Zone(coordinator, system_id, zone_id))

    async_add_entities(zones)
    await coordinator.async_config_entry_first_refresh()

class MyCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, auth):
        super().__init__(
            hass,
            _LOGGER,
            name="Carrier Infinity - %{auth.username}",
            update_interval=timedelta(seconds=60),
        )
        self.auth = auth

    async def _async_update_data(self):
        systems = await python_carrier_infinity.get_systems(self.auth)
        data = {}
        for (system_id, system) in systems.items():
            system_data = {}
            system_data["config"] = await system.get_config()
            system_data["status"] = await system.get_status()
            data[system_id] = system_data
        return data

class Zone(CoordinatorEntity, ClimateEntity):
    def __init__(self, coordinator, system_id, zone_id):
        super().__init__(coordinator, context=(system_id, zone_id))
        self._system_id = system_id
        self._zone_id = zone_id
        self._current_temperature = None

    def _handle_coordinator_update(self) -> None:
        system_data = self.coordinator.data[self._system_id]
        status = system_data["status"].zones[self._zone_id]
        print(status)
        self._current_temperature = status.temperature
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
    def current_temperature(self) -> float | None:
        return self._current_temperature

    @property
    def hvac_mode(self) -> HVACMode | None:
        return None


