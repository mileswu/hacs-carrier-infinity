"""Platform for climate integration."""
from __future__ import annotations
import time

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature
from homeassistant.components.climate import ATTR_TEMPERATURE, ATTR_TARGET_TEMP_LOW, ATTR_TARGET_TEMP_HIGH
from homeassistant.components.climate.const import HVACMode, FAN_OFF, FAN_LOW, FAN_MEDIUM, FAN_HIGH
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
# from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

import python_carrier_infinity
from python_carrier_infinity.types import ActivityName, FanSpeed, Mode, TemperatureUnits

from .const import DOMAIN

PER_SCHEDULE = "per_schedule"

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
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL, HVACMode.HEAT, HVACMode.HEAT_COOL, HVACMode.FAN_ONLY]
    _attr_fan_modes = [FAN_OFF, FAN_LOW, FAN_MEDIUM, FAN_HIGH]
    _attr_preset_modes = [activity.value for activity in ActivityName] + [PER_SCHEDULE]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE | ClimateEntityFeature.FAN_MODE | ClimateEntityFeature.PRESET_MODE
    _attr_translation_key = DOMAIN

    # initialization values
    _attr_fan_mode = None
    _attr_hvac_mode = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
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
            identifiers={(DOMAIN, system.serial)},
            name=system.name,
            manufacturer="Carrier",
            model="Infinity System"
        )

    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data

        if data.status.temperature_units == TemperatureUnits.CELCIUS:
            self._attr_temperature_unit = UnitOfTemperature.CELSIUS
            self._attr_min_temp = 12.0
            self._attr_max_temp = 30.0
            self._attr_target_temperature_step = 0.5
        elif data.status.temperature_units == TemperatureUnits.FARENHEIT:
            self._attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
            self._attr_min_temp = 52.0
            self._attr_max_temp = 88.0
            self._attr_target_temperature_step = 1.0
        else:
            raise ValueError("TemperatureUnits not handled", data.status.temperature_units)

        if data.status.current_indoor_operation != "off":
            self._attr_hvac_action = data.status.current_indoor_operation
        else:
            self._attr_hvac_action = data.status.current_outdoor_operation

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

    async def async_set_hvac_mode(self, hvac_mode):
        self._attr_target_temperature = None
        self._attr_target_temperature_low = None
        self._attr_target_temperature_high = None
        activity = self.coordinator.data.status.zones[self.zone_id].activity
        activity_config = self.coordinator.data.config.zones[self.zone_id].activities[activity]

        if hvac_mode == HVACMode.OFF:
            mode = Mode.OFF
        elif hvac_mode == HVACMode.COOL:
            mode = Mode.COOL
            self._attr_target_temperature = activity_config.target_cooling_temperature
        elif hvac_mode == HVACMode.HEAT:
            mode = Mode.HEAT
            self._attr_target_temperature = activity_config.target_heating_temperature
        elif hvac_mode == HVACMode.HEAT_COOL:
            mode = Mode.AUTO
            self._attr_target_temperature_low = activity_config.target_heating_temperature
            self._attr_target_temperature_high = activity_config.target_cooling_temperature
        elif hvac_mode == HVACMode.FAN_ONLY:
            mode = mode.FAN_ONLY
        else:
            raise ValueError("hvac_mode not handled", hvac_mode)

        await self.system.set_mode(mode)
        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()


    async def async_set_preset_mode(self, preset_mode):
        if preset_mode == PER_SCHEDULE:
            await self.system.set_zone_activity_hold(self.zone_id, None, None)
            time.sleep(5.0)
            await self.coordinator.async_refresh()
        else:
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

    async def async_set_fan_mode(self, fan_mode):
        if fan_mode == FAN_OFF:
            fan = FanSpeed.OFF
        elif fan_mode == FAN_LOW:
            fan = FanSpeed.LOW
        elif fan_mode == FAN_MEDIUM:
            fan = FanSpeed.MED
        elif fan_mode == FAN_HIGH:
            fan = FanSpeed.HIGH
        else:
            raise ValueError("fan_mode not handled", fan_mode)

        await self.system.set_zone_activity_fan(self.zone_id, self._attr_preset_mode, fan)
        self._attr_fan_mode = fan
        self.async_write_ha_state()
