"""Provides the GlowSwitch DataUpdateCoordinator."""
from __future__ import annotations

import asyncio
import contextlib
import logging

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothDataUpdateCoordinator,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from bleak.backends.device import BLEDevice

from .generic_bt_api.device import GlowSwitchDevice
from .const import DOMAIN, DEVICE_STARTUP_TIMEOUT_SECONDS

_LOGGER = logging.getLogger(__name__)


class GlowSwitchCoordinator(PassiveBluetoothDataUpdateCoordinator):
    """
    Coordinator to manage GlowSwitch device availability.
    
    This coordinator is passive and does not poll the device. It relies on
    Bluetooth advertisement events to determine device availability.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        ble_device: BLEDevice,
        device: GlowSwitchDevice,
        device_name: str,
        base_unique_id: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger,
            ble_device.address,
            bluetooth.BluetoothScanningMode.PASSIVE,
        )
        self.ble_device = ble_device
        self.device = device
        self.device_name = device_name
        self.base_unique_id = base_unique_id
        self._ready_event = asyncio.Event()

    @property
    def device_info(self):
        """Return device information."""
        return {
            "connections": {(dr.CONNECTION_BLUETOOTH, self.ble_device.address)},
            "name": self.device_name,
        }

    @callback
    def _async_handle_bluetooth_event(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Handle a Bluetooth event to update availability."""
        super()._async_handle_bluetooth_event(service_info, change)
        self.ble_device = service_info.device
        _LOGGER.debug(f"Availability updated for {self.device_name}: {self.available}")
        self._ready_event.set()

    async def async_wait_ready(self) -> bool:
        """Wait for the device to be ready (first advertisement)."""
        with contextlib.suppress(asyncio.TimeoutError):
            async with asyncio.timeout(DEVICE_STARTUP_TIMEOUT_SECONDS):
                await self._ready_event.wait()
                return True
        return False
