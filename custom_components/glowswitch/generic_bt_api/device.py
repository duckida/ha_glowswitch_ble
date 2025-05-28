"""generic bt device"""

from uuid import UUID
import asyncio
import logging
from contextlib import AsyncExitStack

from bleak import BleakClient
from bleak.exc import BleakError

_LOGGER = logging.getLogger(__name__)


class GenericBTDevice:
    """Generic BT Device Class"""
    def __init__(self, ble_device):
        self._ble_device = ble_device
        self._client: BleakClient | None = None
        self._client_stack = AsyncExitStack()
        self._lock = asyncio.Lock()

    async def update(self):
        pass

    async def stop(self):
        _LOGGER.debug("Stopping GenericBTDevice, ensuring client is disconnected.")
        async with self._lock:
            if self._client:
                _LOGGER.debug("Closing client stack due to stop call.")
                await self._client_stack.pop_all().aclose()
            self._client = None
            self._client_stack = AsyncExitStack() # Re-initialize just in case

    @property
    def connected(self):
        return not self._client is None

    async def get_client(self):
        async with self._lock:
            if not self._client:
                _LOGGER.debug("Connecting")
                try:
                    self._client = await self._client_stack.enter_async_context(BleakClient(self._ble_device, timeout=30))
                except asyncio.TimeoutError as exc:
                    _LOGGER.debug("Timeout on connect", exc_info=True)
                    raise IdealLedTimeout("Timeout on connect") from exc
                except BleakError as exc:
                    _LOGGER.debug("Error on connect", exc_info=True)
                    raise IdealLedBleakError("Error on connect") from exc
            else:
                _LOGGER.debug("Connection reused")

    async def ensure_connected_and_services_discovered(self):
        _LOGGER.debug("Attempting to ensure client is connected and services are discovered.")
        try:
            # Step 1: Ensure client is available and connected.
            # get_client() will attempt to connect or reconnect if self._client is None or becomes invalid.
            # It will raise an error if connection fails.
            await self.get_client()

            # Step 2: Explicitly discover/re-discover services.
            # We need to ensure self._client is not None after get_client() call.
            if not self._client:
                _LOGGER.warning("No client available after get_client attempt. Cannot discover services.")
                # Raise an exception or return a status indicating failure
                raise BleakError("Failed to establish a client connection.")

            # At this point, self._client should be a connected BleakClient instance.
            # BleakClient itself attempts service discovery on connect.
            # Calling get_services() here is an explicit way to ensure it's done
            # or to re-trigger it if necessary.
            _LOGGER.debug("Client available, explicitly calling get_services().")
            await self._client.get_services()
            _LOGGER.debug("Service discovery call completed.")

        except BleakError as e:
            _LOGGER.error(f"BleakError during ensure_connected_and_services_discovered: {e}", exc_info=True)
            # Re-raise the original BleakError to be handled by the caller (light.py)
            raise
        except Exception as e:
            # Catch any other unexpected errors
            _LOGGER.error(f"Unexpected error during ensure_connected_and_services_discovered: {e}", exc_info=True)
            # Wrap in a BleakError or a custom error if appropriate, then re-raise
            raise BleakError(f"Unexpected issue in ensure_connected_and_services_discovered: {e}") from e

    async def write_gatt(self, target_uuid, data):
        await self.get_client()
        uuid_str = "{" + target_uuid + "}"
        uuid = UUID(uuid_str)
        data_as_bytes = bytearray.fromhex(data)
        try:
            await self._client.write_gatt_char(uuid, data_as_bytes, True)
        except BleakError as e:
            if "service discovery not yet completed" in str(e).lower():
                _LOGGER.debug("Service discovery not yet completed on write, attempting to rediscover services and retry.")
                await self._client.get_services()
                await self._client.write_gatt_char(uuid, data_as_bytes, True)
            else:
                raise e

    async def read_gatt(self, target_uuid):
        await self.get_client()
        uuid_str = "{" + target_uuid + "}"
        uuid = UUID(uuid_str)
        try:
            data = await self._client.read_gatt_char(uuid)
            print(data)
            return data
        except BleakError as e:
            if "service discovery not yet completed" in str(e).lower():
                _LOGGER.debug("Service discovery not yet completed on read, attempting to rediscover services and retry.")
                await self._client.get_services()
                return await self._client.read_gatt_char(uuid)
            else:
                raise e

    async def update_from_advertisement(self, advertisement):
        _LOGGER.debug("Device available after being unavailable (reconnect or fresh advertisement). Resetting BLE client to ensure fresh connection and service discovery.")
        async with self._lock:
            if self._client:
                _LOGGER.debug("Closing existing client stack.")
                await self._client_stack.pop_all().aclose()
            self._client = None
            self._client_stack = AsyncExitStack() # Re-initialize for future connections
