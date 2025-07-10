from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import GlowSwitchCoordinator
from .entity import GlowSwitchEntity
from .generic_bt_api.device import GlowSwitchBleakError, GlowSwitchTimeout

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the GlowSwitch light from a config entry."""
    coordinator: GlowSwitchCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([GlowSwitchLight(coordinator, entry)])


class GlowSwitchLight(GlowSwitchEntity, LightEntity):
    """
    Representation of a GlowSwitch Light.

    This entity uses an assumed state model.
    """

    _attr_name = None  # Use the device name as the entity name
    _attr_assumed_state = True

    def __init__(self, coordinator: GlowSwitchCoordinator, entry: ConfigEntry) -> None:
        """Initialize the light."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id}_light"
        self._device_type = entry.data.get("device_type", "glowswitch")

        # Set initial state
        self._attr_is_on = False
        self._attr_brightness = None

        # Set supported color modes based on device type
        if self._device_type == "glowdim":
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
            self._attr_color_mode = ColorMode.BRIGHTNESS
            self._attr_brightness = 255  # Default brightness
        else:
            self._attr_supported_color_modes = {ColorMode.ONOFF}
            self._attr_color_mode = ColorMode.ONOFF

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        _LOGGER.debug(f"Turning on '{self.name}'")
        command = bytearray()

        if self._device_type == "glowdim":
            ha_brightness = kwargs.get(ATTR_BRIGHTNESS, self.brightness or 255)
            
            # Convert HA brightness (0-255) to device brightness (0-100)
            device_brightness = max(0, min(100, round(ha_brightness / 255 * 100)))
            
            if device_brightness == 0:
                # A brightness of 0 is equivalent to turning off
                await self.async_turn_off()
                return

            command.append(device_brightness)
            self._attr_brightness = ha_brightness
        else:
            command.append(0x01)

        try:
            await self._device.send_command(command)
            self._attr_is_on = True
            self.async_write_ha_state()
        except (GlowSwitchBleakError, GlowSwitchTimeout) as e:
            _LOGGER.error(f"Error turning on '{self.name}': {e}")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        _LOGGER.debug(f"Turning off '{self.name}'")
        command = bytearray([0x00])

        try:
            await self._device.send_command(command)
            self._attr_is_on = False
            self.async_write_ha_state()
        except (GlowSwitchBleakError, GlowSwitchTimeout) as e:
            _LOGGER.error(f"Error turning off '{self.name}': {e}")
