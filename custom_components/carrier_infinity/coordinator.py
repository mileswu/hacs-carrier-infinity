from homeassistant.helpers.update_coordinator import     DataUpdateCoordinator
import logging
from datetime import timedelta

_LOGGER = logging.getLogger(__name__)

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
        print("FETCH")
        config = await self.system.get_config()
        status = await self.system.get_status()
        return CoordinatorUpdate(self.system, config, status)

class CoordinatorUpdate():
    def __init__(self, system, config, status):
        self.system = system
        self.config = config
        self.status = status

