from __future__ import annotations

import logging
from typing import Any # Added for **kwargs

from homeassistant.components.light import LightEntity # LightEntityFeature removed
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import GenericBTCoordinator # Changed import
from .entity import GenericBTEntity # Changed import

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GenericBTCoordinator = hass.data[DOMAIN][entry.entry_id] # Changed type hint
    async_add_entities([GenericBTLight(coordinator, entry)]) # Renamed class

class GenericBTLight(GenericBTEntity, LightEntity): # Renamed class and inheritance
    # _attr_supported_features removed to rely on defaults for a basic on/off light
    _attr_name = "GlowSwitch Light" # Name can remain

    def __init__(self, coordinator: GenericBTCoordinator, entry: ConfigEntry) -> None: # Changed type hint
        super().__init__(coordinator)
        self._entry = entry
        # Assuming a unique ID for the light entity based on the entry's unique ID.
        self._attr_unique_id = f"{entry.unique_id}_light"
        # _attr_device_info will be inherited from GlowSwitchEntity or set via coordinator property
        # self._attr_device_info = self.coordinator.device_info

        # Initialize state.
        self._is_on = None # Or False by default

    @property
    def is_on(self) -> bool | None:
        """Return true if the light is on."""
        return self._is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        try:
            # Using the placeholder UUID and value
            await self._device.write_gatt("12345678-1234-5678-1234-56789abcdef1", "01")
            self._is_on = True
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"Error turning on light: {e}")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        try:
            # Using the placeholder UUID and value
            await self._device.write_gatt("12345678-1234-5678-1234-56789abcdef1", "00")
            self._is_on = False
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"Error turning off light: {e}")
