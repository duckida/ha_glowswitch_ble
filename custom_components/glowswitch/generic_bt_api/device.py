"""generic bt device"""

from uuid import UUID
import asyncio
import logging
from contextlib import AsyncExitStack

from bleak import BleakClient
from bleak.exc import BleakError

_LOGGER = logging.getLogger(__name__)


class IdealLedTimeout(Exception):
    """Custom timeout exception."""

class IdealLedBleakError(Exception):
    """Custom BleakError wrapper."""


class GenericBTDevice:
    """Generic BT Device Class"""
    def __init__(self, ble_device):
        self._ble_device = ble_device
        self._lock = asyncio.Lock()

    async def update(self):
        pass

    async def stop(self):
            pass

    async def write_gatt(self, target_uuid, data):
        async with self._lock:
            async with AsyncExitStack() as stack:
                try:
                    client = await stack.enter_async_context(BleakClient(self._ble_device, timeout=30))
                    _LOGGER.debug(f"Connected to {self._ble_device.address} for write")

                    uuid_str = "{" + target_uuid + "}"
                    uuid = UUID(uuid_str)
                    data_as_bytes = bytearray.fromhex(data)
                    await client.write_gatt_char(uuid, data_as_bytes, True)
                    _LOGGER.debug(f"Data written to {uuid_str}")
                except asyncio.TimeoutError as exc:
                    _LOGGER.warning(f"Timeout on write to {self._ble_device.address}: {exc}")
                    raise IdealLedTimeout(f"Timeout on write to {self._ble_device.address}") from exc
                except BleakError as exc:
                    _LOGGER.warning(f"BleakError on write to {self._ble_device.address}: {exc}")
                    raise IdealLedBleakError(f"BleakError on write to {self._ble_device.address}") from exc

    async def read_gatt(self, target_uuid):
        async with self._lock:
            async with AsyncExitStack() as stack:
                try:
                    client = await stack.enter_async_context(BleakClient(self._ble_device, timeout=30))
                    _LOGGER.debug(f"Connected to {self._ble_device.address} for read")

                    uuid_str = "{" + target_uuid + "}"
                    uuid = UUID(uuid_str)
                    data = await client.read_gatt_char(uuid)
                    _LOGGER.debug(f"Data read from {uuid_str}: {data.hex()}")
                    return data
                except asyncio.TimeoutError as exc:
                    _LOGGER.warning(f"Timeout on read from {self._ble_device.address}: {exc}")
                    raise IdealLedTimeout(f"Timeout on read from {self._ble_device.address}") from exc
                except BleakError as exc:
                    _LOGGER.warning(f"BleakError on read from {self._ble_device.address}: {exc}")
                    raise IdealLedBleakError(f"BleakError on read from {self._ble_device.address}") from exc

    def update_from_advertisement(self, advertisement):
        pass
