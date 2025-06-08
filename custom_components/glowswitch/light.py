from __future__ import annotations

import logging
from typing import Any # Added for **kwargs

from homeassistant.components.light import ColorMode, LightEntity, LightEntityFeature, ATTR_BRIGHTNESS
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
        self._attr_unique_id = f"{entry.unique_id}_light"

        self._device_type = entry.data.get("device_type", "glowswitch") # Default to glowswitch if not set
        self._is_on = None # Or False by default
        self._brightness = 255 if self._device_type == "glowdim" else None # HA brightness 0-255

    @property
    def supported_features(self) -> LightEntityFeature:
        """Flag supported features."""
        # BRIGHTNESS is handled by color_modes. Other features like EFFECT could be added here.
        return LightEntityFeature(0)

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        """Return the set of supported color modes."""
        if self._device_type == "glowdim":
            return {ColorMode.BRIGHTNESS}
        return {ColorMode.ONOFF}

    @property
    def color_mode(self) -> ColorMode:
        """Return the current color mode of the light."""
        if self._device_type == "glowdim":
            return ColorMode.BRIGHTNESS
        return ColorMode.ONOFF

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        if self._device_type == "glowdim":
            return self._brightness
        return None

    @property
    def is_on(self) -> bool | None:
        """Return true if the light is on."""
        return self._is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        try:
            if self._device_type == "glowdim":
                ha_brightness = kwargs.get(ATTR_BRIGHTNESS)
                if ha_brightness is not None:
                    self._brightness = ha_brightness
                # If self._brightness is None (e.g. first turn_on and not specified), default to full.
                # self._brightness should have been initialized to 255 for glowdim.
                current_ha_brightness = self._brightness if self._brightness is not None else 255

                # Convert HA brightness (0-255) to device brightness (0-100)
                device_brightness_value = round(current_ha_brightness / 255 * 100)
                # Ensure value is within 0-100 range
                device_brightness_value = max(0, min(100, device_brightness_value))
                hex_data = f"{device_brightness_value:02x}"
                _LOGGER.debug(f"Turning on {self.name} ({self._device_type}) to brightness {current_ha_brightness}/255 -> device value {device_brightness_value}/100 -> hex string {hex_data}")
                await self._device.write_gatt("12345678-1234-5678-1234-56789abcdef1", hex_data)
            else: # glowswitch
                _LOGGER.debug(f"Turning on {self.name} ({self._device_type})")
                await self._device.write_gatt("12345678-1234-5678-1234-56789abcdef1", "01")

            self._is_on = True
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"Error turning on light {self.name}: {e}")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        try:
            if self._device_type == "glowdim":
                _LOGGER.debug(f"Turning off {self.name} ({self._device_type})")
                await self._device.write_gatt("12345678-1234-5678-1234-56789abcdef1", "00")
            else: # glowswitch
                _LOGGER.debug(f"Turning off {self.name} ({self._device_type})")
                await self._device.write_gatt("12345678-1234-5678-1234-56789abcdef1", "00")

            self._is_on = False
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"Error turning off light {self.name}: {e}")
