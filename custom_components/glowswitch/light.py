from __future__ import annotations

import logging
from typing import Any

from bleak.exc import BleakError  # Added
from homeassistant.components.light import LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError  # Added
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import GenericBTCoordinator
from .entity import GenericBTEntity

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GenericBTCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([GenericBTLight(coordinator, entry)])

class GenericBTLight(GenericBTEntity, LightEntity):
    _attr_name = "GlowSwitch Light"

    def __init__(self, coordinator: GenericBTCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id}_light"
        self._is_on = None

    @property
    def is_on(self) -> bool | None:
        """Return true if the light is on."""
        return self._is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        characteristic_uuid = "12345678-1234-5678-1234-56789abcdef1"  # Placeholder
        value_to_write = "01"  # Placeholder

        try:
            await self._device.write_gatt(characteristic_uuid, value_to_write)
            self._is_on = True
            self.async_write_ha_state()
        except BleakError as e:
            _LOGGER.warning(f"Turn on: First attempt failed (BleakError: {e}). Attempting recovery and retry.")
            try:
                await self._device.ensure_connected_and_services_discovered()
                _LOGGER.info("Turn on: Recovery successful. Retrying GATT write.")
                await self._device.write_gatt(characteristic_uuid, value_to_write)
                self._is_on = True
                self.async_write_ha_state()
                _LOGGER.info("Turn on: Retry successful.")
            except BleakError as retry_e:
                _LOGGER.error(f"Turn on: Retry failed (BleakError: {retry_e}).", exc_info=True)
                raise HomeAssistantError(f"Failed to turn on light after retry: {retry_e}") from retry_e
            except Exception as general_retry_e:
                _LOGGER.error(f"Turn on: Retry failed (General Exception: {general_retry_e}).", exc_info=True)
                raise HomeAssistantError(f"Failed to turn on light after retry due to unexpected error: {general_retry_e}") from general_retry_e
        except Exception as e:
            _LOGGER.error(f"Turn on: Initial attempt failed (General Exception: {e}).", exc_info=True)
            if not isinstance(e, HomeAssistantError):
                raise HomeAssistantError(f"Failed to turn on light due to unexpected error: {e}") from e
            else:
                raise

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        characteristic_uuid = "12345678-1234-5678-1234-56789abcdef1"  # Placeholder
        value_to_write = "00"  # Placeholder

        try:
            await self._device.write_gatt(characteristic_uuid, value_to_write)
            self._is_on = False
            self.async_write_ha_state()
        except BleakError as e:
            _LOGGER.warning(f"Turn off: First attempt failed (BleakError: {e}). Attempting recovery and retry.")
            try:
                await self._device.ensure_connected_and_services_discovered()
                _LOGGER.info("Turn off: Recovery successful. Retrying GATT write.")
                await self._device.write_gatt(characteristic_uuid, value_to_write)
                self._is_on = False
                self.async_write_ha_state()
                _LOGGER.info("Turn off: Retry successful.")
            except BleakError as retry_e:
                _LOGGER.error(f"Turn off: Retry failed (BleakError: {retry_e}).", exc_info=True)
                raise HomeAssistantError(f"Failed to turn off light after retry: {retry_e}") from retry_e
            except Exception as general_retry_e:
                _LOGGER.error(f"Turn off: Retry failed (General Exception: {general_retry_e}).", exc_info=True)
                raise HomeAssistantError(f"Failed to turn off light after retry due to unexpected error: {general_retry_e}") from general_retry_e
        except Exception as e:
            _LOGGER.error(f"Turn off: Initial attempt failed (General Exception: {e}).", exc_info=True)
            if not isinstance(e, HomeAssistantError):
                raise HomeAssistantError(f"Failed to turn off light due to unexpected error: {e}") from e
            else:
                raise
