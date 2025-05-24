"""Support for Generic BT binary sensor."""
from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, Schema
from .coordinator import GenericBTCoordinator # Updated import
from .entity import GenericBTEntity # Updated import


# Initialize the logger
_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up GlowSwitch device based on a config entry.""" # Docstring can remain
    coordinator: GenericBTCoordinator = hass.data[DOMAIN][entry.entry_id] # Updated type hint
    async_add_entities([GenericBTBinarySensor(coordinator)]) # Updated class name

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service("write_gatt", Schema.WRITE_GATT.value, "write_gatt")
    platform.async_register_entity_service("read_gatt", Schema.READ_GATT.value, "read_gatt")


class GenericBTBinarySensor(GenericBTEntity, BinarySensorEntity): # Updated class name and base class
    """Representation of a GlowSwitch Binary Sensor.""" # Docstring can remain

    _attr_name = None # Or "Generic BT Binary Sensor" or "GlowSwitch Binary Sensor" - keeping as is for now

    def __init__(self, coordinator: GenericBTCoordinator) -> None: # Updated type hint
        """Initialize the Device."""
        super().__init__(coordinator)

    @property
    def is_on(self):
        return self._device.connected

    async def write_gatt(self, target_uuid, data):
        await self._device.write_gatt(target_uuid, data)
        self.async_write_ha_state()

    async def read_gatt(self, target_uuid):
        await self._device.read_gatt(target_uuid)
        self.async_write_ha_state()


