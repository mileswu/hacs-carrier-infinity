"""Platform for climate integration."""
from __future__ import annotations


from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature
from homeassistant.components.climate import ATTR_TEMPERATURE, ATTR_TARGET_TEMP_LOW, ATTR_TARGET_TEMP_HIGH
from homeassistant.components.climate.const import HVACMode, FAN_OFF, FAN_LOW, FAN_MEDIUM, FAN_HIGH
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
# from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

import python_carrier_infinity
from python_carrier_infinity.types import ActivityName, FanSpeed, Mode, TemperatureUnits

from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities) -> None:
    systems_and_coordinators = hass.data[DOMAIN][entry.entry_id]

    zones = []
    for (system, coordinator) in systems_and_coordinators:
        config = await system.get_config()
        for zone_config in config.zones.values():
            zones.append(Zone(coordinator, system, zone_config))

    async_add_entities(zones)

class Zone(CoordinatorEntity, ClimateEntity):
    _attr_has_entity_name = True
    _attr_name = None
    _attr_precision = 1.0
    _attr_target_temperature_step = 1.0
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL, HVACMode.HEAT, HVACMode.HEAT_COOL, HVACMode.FAN_ONLY]
    _attr_fan_modes = [FAN_OFF, FAN_LOW, FAN_MEDIUM, FAN_HIGH]
    _attr_preset_modes = [activity.value for activity in ActivityName]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE | ClimateEntityFeature.FAN_MODE | ClimateEntityFeature.PRESET_MODE

    # initialization values
    _attr_fan_mode = None
    _attr_hvac_mode = None
    _attr_temperature_unit = TEMP_CELSIUS
    _attr_target_temperature_low = None
    _attr_target_temperature_high = None
    _attr_preset_mode = None

    def __init__(self, coordinator, system, zone_config):
        super().__init__(coordinator)
        self.system = system
        self.zone_id = zone_config.id
        self._attr_unique_id = f"{system.serial}-{zone_config.id}"
        self._attr_name = zone_config.name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name=system.name,
            manufacturer="Carrier",
            model="Infinity System"
        )

    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data

        if data.status.temperature_units == TemperatureUnits.CELCIUS:
            self._attr_temperature_unit = TEMP_CELSIUS
        elif data.status.temperature_units == TemperatureUnits.FARENHEIT:
            self._attr_temperature_unit = TEMP_FAHRENHEIT
        else:
            raise ValueError("TemperatureUnits not handled", data.status.temperature_units)

        self._attr_hvac_action = data.status.current_operation
        self._attr_current_temperature = data.status.zones[self.zone_id].temperature
        self._attr_current_humidity = data.status.zones[self.zone_id].relative_humidity
        self._attr_preset_mode = data.status.zones[self.zone_id].activity.value
        self._attr_target_temperature = None
        self._attr_target_temperature_low = None
        self._attr_target_temperature_high = None

        if data.config.mode == Mode.OFF:
            self._attr_hvac_mode = HVACMode.OFF
        elif data.config.mode == Mode.COOL:
            self._attr_hvac_mode = HVACMode.COOL
            self._attr_target_temperature = data.status.zones[self.zone_id].target_cooling_temperature
        elif data.config.mode == Mode.HEAT:
            self._attr_hvac_mode = HVACMode.HEAT
            self._attr_target_temperature = data.status.zones[self.zone_id].target_heating_temperature
        elif data.config.mode == Mode.AUTO:
            self._attr_hvac_mode = HVACMode.HEAT_COOL
            self._attr_target_temperature_low = data.status.zones[self.zone_id].target_heating_temperature
            self._attr_target_temperature_high = data.status.zones[self.zone_id].target_cooling_temperature
        elif data.config.mode == Mode.FAN_ONLY:
            self._attr_hvac_mode = HVACMode.FAN_ONLY
        else:
            raise ValueError("Mode not handled", data.status.mode)

        if data.status.zones[self.zone_id].fan_speed == FanSpeed.OFF:
            self._attr_fan_mode = FAN_OFF
        elif data.status.zones[self.zone_id].fan_speed == FanSpeed.LOW:
            self._attr_fan_mode = FAN_LOW
        elif data.status.zones[self.zone_id].fan_speed == FanSpeed.MED:
            self._attr_fan_mode = FAN_MEDIUM
        elif data.status.zones[self.zone_id].fan_speed == FanSpeed.HIGH:
            self._attr_fan_mode = FAN_HIGH
        else:
            raise ValueError("FanSpeed not handled", data.status.zones[self.zone_id].fan_speed)

        self.async_write_ha_state()


    async def async_set_preset_mode(self, preset_mode):
        activity = ActivityName(preset_mode)
        await self.system.set_zone_activity_hold(self.zone_id, activity, None)
        self._attr_preset_mode = preset_mode

        zone_config = self.coordinator.data.config.zones[self.zone_id]
        if self._attr_hvac_mode == HVACMode.COOL:
            self._attr_target_temperature = zone_config.activities[activity].target_cooling_temperature
        elif self._attr_hvac_mode == HVACMode.HEAT:
            self._attr_target_temperature = zone_config.activities[activity].target_heating_temperature
        elif self._attr_hvac_mode == HVACMode.HEAT_COOL:
            self._attr_target_temperature_high = zone_config.activities[activity].target_cooling_temperature
            self._attr_target_temperature_low = zone_config.activities[activity].target_heating_temperature
        self._attr_fan_mode = zone_config.activities[activity].fan_speed

        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs):
        data = self.coordinator.data
        zone_config = data.config.zones[self.zone_id]
        cool_temp = data.status.zones[self.zone_id].target_cooling_temperature
        heat_temp = data.status.zones[self.zone_id].target_heating_temperature

        if zone_config.hold_activity != ActivityName.MANUAL or zone_config.hold_until is not None:
            await self.system.set_zone_activity_hold(self.zone_id, ActivityName.MANUAL, None)
        self._attr_preset_mode = ActivityName.MANUAL

        if self._attr_hvac_mode == HVACMode.COOL:
            cool_temp = kwargs.get(ATTR_TEMPERATURE)
            self._attr_target_temperature = cool_temp
        elif self._attr_hvac_mode == HVACMode.HEAT:
            heat_temp = kwargs.get(ATTR_TEMPERATURE)
            self._attr_target_temperature = heat_temp
        elif self._attr_hvac_mode == HVACMode.HEAT_COOL:
            cool_temp = kwargs.get(ATTR_TARGET_TEMP_HIGH)
            heat_temp = kwargs.get(ATTR_TARGET_TEMP_LOW)
            self._attr_target_temperature_low = heat_temp
            self._attr_target_temperature_high = cool_temp

        await self.system.set_zone_activity_temp(self.zone_id, ActivityName.MANUAL, cool_temp, heat_temp)
        self.async_write_ha_state()
