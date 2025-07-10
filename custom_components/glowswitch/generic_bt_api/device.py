"""GlowSwitch Bluetooth Device"""

from uuid import UUID
import asyncio
import logging
from contextlib import AsyncExitStack

from bleak import BleakClient
from bleak.exc import BleakError

_LOGGER = logging.getLogger(__name__)

LIGHT_CHARACTERISTIC_UUID = "12345678-1234-5678-1234-56789abcdef1"


class GlowSwitchTimeout(Exception):
    """Custom timeout exception."""


class GlowSwitchBleakError(Exception):
    """Custom BleakError wrapper."""


class GlowSwitchDevice:
    """
    Represents a GlowSwitch device, handling the connection and commands.
    """

    def __init__(self, ble_device):
        self._ble_device = ble_device
        self._lock = asyncio.Lock()

    def update_device(self, ble_device):
        """Update the BLEDevice object."""
        self._ble_device = ble_device

    async def send_command(self, data: bytearray):
        """Connects to the device, sends a command, and disconnects."""
        async with self._lock:
            try:
                async with BleakClient(self._ble_device, timeout=15) as client:
                    _LOGGER.debug(f"Connected to {self._ble_device.address} to send command: {data.hex()}")
                    await client.write_gatt_char(
                        LIGHT_CHARACTERISTIC_UUID, data, response=True
                    )
                    _LOGGER.debug("Command sent successfully")
            except asyncio.TimeoutError as exc:
                raise GlowSwitchTimeout(
                    f"Timeout sending command to {self._ble_device.address}"
                ) from exc
            except BleakError as exc:
                _LOGGER.exception(
                    f"BleakError sending command to {self._ble_device.address}"
                )
                raise GlowSwitchBleakError(
                    f"Error sending command to {self._ble_device.address}: {exc}"
                ) from exc
