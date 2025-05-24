"""Support for Generic BT binary sensor."""
from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, Schema
from .coordinator import GlowSwitchCoordinator
from .entity import GlowSwitchEntity


# Initialize the logger
_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up GlowSwitch device based on a config entry."""
    coordinator: GlowSwitchCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([GlowSwitchBinarySensor(coordinator)])

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service("write_gatt", Schema.WRITE_GATT.value, "write_gatt")
    platform.async_register_entity_service("read_gatt", Schema.READ_GATT.value, "read_gatt")


class GlowSwitchBinarySensor(GlowSwitchEntity, BinarySensorEntity):
    """Representation of a GlowSwitch Binary Sensor."""

    _attr_name = None

    def __init__(self, coordinator: GlowSwitchCoordinator) -> None:
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


