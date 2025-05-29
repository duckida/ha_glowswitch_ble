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
        # This property might need adjustment based on the new get_client logic
        # For now, it reflects if a client object exists.
        # A more accurate check would be self._client and self._client.is_connected
        return self._client is not None and self._client.is_connected

    async def get_client(self):
        async with self._lock:
            # Check if client exists but is not connected
            if self._client and not self._client.is_connected:
                _LOGGER.debug(f"Existing client for {self._ble_device.address} found but not connected. Cleaning up and forcing reconnect.")
                try:
                    await self._client_stack.pop_all().aclose()
                except Exception as e:
                    _LOGGER.debug(f"Exception during client_stack.pop_all().aclose() for {self._ble_device.address}: {e}", exc_info=True)
                self._client = None
                self._client_stack = AsyncExitStack() # Re-initialize for a fresh connection

            # Proceed to connect if no client exists (or was just cleared)
            if not self._client:
                _LOGGER.debug(f"No active client or client was cleared for {self._ble_device.address}. Attempting new connection.")
                # Ensure self._ble_device is up-to-date before connecting.
                if not self._ble_device:
                    _LOGGER.error("No BLE device set, cannot connect.")
                    raise BleakError("BLE device not available for connection.")
                
                try:
                    self._client = await self._client_stack.enter_async_context(BleakClient(self._ble_device, timeout=30))
                    _LOGGER.debug(f"Successfully connected to {self._ble_device.address}.")
                except asyncio.TimeoutError as exc:
                    _LOGGER.error(f"Timeout connecting to {self._ble_device.address}.", exc_info=True)
                    try:
                        await self._client_stack.pop_all().aclose()
                    except Exception as e_close: # Added try-except for robustness
                        _LOGGER.debug(f"Exception during stack cleanup after TimeoutError for {self._ble_device.address}: {e_close}", exc_info=True)
                    self._client_stack = AsyncExitStack()
                    self._client = None 
                    raise BleakError(f"Timeout on connect to {self._ble_device.address}") from exc
                except BleakError as exc:
                    _LOGGER.error(f"BleakError connecting to {self._ble_device.address}: {exc}", exc_info=True)
                    try:
                        await self._client_stack.pop_all().aclose()
                    except Exception as e_close: # Added try-except for robustness
                        _LOGGER.debug(f"Exception during stack cleanup after BleakError for {self._ble_device.address}: {e_close}", exc_info=True)
                    self._client_stack = AsyncExitStack()
                    self._client = None 
                    raise 
                except Exception as exc: 
                    _LOGGER.error(f"Unexpected error connecting to {self._ble_device.address}: {exc}", exc_info=True)
                    try:
                        await self._client_stack.pop_all().aclose()
                    except Exception as e_close: # Added try-except for robustness
                        _LOGGER.debug(f"Exception during stack cleanup after UnexpectedError for {self._ble_device.address}: {e_close}", exc_info=True)
                    self._client_stack = AsyncExitStack()
                    self._client = None 
                    raise BleakError(f"Unexpected error on connect to {self._ble_device.address}: {exc}") from exc
            else:
                _LOGGER.debug(f"Reusing existing connected client for {self._ble_device.address}.")
            return self._client

    async def ensure_connected_and_services_discovered(self):
        _LOGGER.debug(f"Attempting to ensure client is connected and services are discovered for {self._ble_device.address}.")
        client = await self.get_client() # Uses the updated get_client
        if not client: # Should not happen if get_client raises errors properly
            _LOGGER.error(f"No client obtained from get_client for {self._ble_device.address}. Cannot discover services.")
            raise BleakError("Failed to establish a client connection.")
        
        try:
            _LOGGER.debug(f"Client for {self._ble_device.address} available, explicitly calling get_services().")
            await client.get_services()
            _LOGGER.debug(f"Service discovery call completed for {self._ble_device.address}.")
        except BleakError as e:
            _LOGGER.error(f"BleakError during service discovery for {self._ble_device.address}: {e}", exc_info=True)
            raise
        except Exception as e:
            _LOGGER.error(f"Unexpected error during service discovery for {self._ble_device.address}: {e}", exc_info=True)
            raise BleakError(f"Unexpected issue in service discovery for {self._ble_device.address}: {e}") from e


    async def write_gatt(self, target_uuid, data):
        client = await self.get_client() # Ensures client is connected
        uuid_str = "{" + target_uuid + "}"
        uuid = UUID(uuid_str)
        data_as_bytes = bytearray.fromhex(data)
        try:
            await client.write_gatt_char(uuid, data_as_bytes, True)
        except BleakError as e:
            if "service discovery not yet completed" in str(e).lower():
                _LOGGER.debug(f"Service discovery not yet completed on write for {self._ble_device.address}, attempting to rediscover services and retry.")
                await client.get_services()
                await client.write_gatt_char(uuid, data_as_bytes, True)
            else:
                _LOGGER.error(f"BleakError during write_gatt for {self._ble_device.address}: {e}", exc_info=True)
                raise
        except Exception as e:
            _LOGGER.error(f"Unexpected error during write_gatt for {self._ble_device.address}: {e}", exc_info=True)
            raise BleakError(f"Unexpected issue in write_gatt for {self._ble_device.address}: {e}") from e


    async def read_gatt(self, target_uuid):
        client = await self.get_client() # Ensures client is connected
        uuid_str = "{" + target_uuid + "}"
        uuid = UUID(uuid_str)
        try:
            data = await client.read_gatt_char(uuid)
            # print(data) # Consider removing or making conditional
            return data
        except BleakError as e:
            if "service discovery not yet completed" in str(e).lower():
                _LOGGER.debug(f"Service discovery not yet completed on read for {self._ble_device.address}, attempting to rediscover services and retry.")
                await client.get_services()
                return await client.read_gatt_char(uuid)
            else:
                _LOGGER.error(f"BleakError during read_gatt for {self._ble_device.address}: {e}", exc_info=True)
                raise
        except Exception as e:
            _LOGGER.error(f"Unexpected error during read_gatt for {self._ble_device.address}: {e}", exc_info=True)
            raise BleakError(f"Unexpected issue in read_gatt for {self._ble_device.address}: {e}") from e


    async def update_from_advertisement(self, advertisement):
        _LOGGER.debug(f"Device {self._ble_device.address if self._ble_device else 'N/A'} available after being unavailable. Resetting BLE client.")
        # Update the internal BLEDevice instance with the new advertisement data
        self._ble_device = advertisement.device 
        async with self._lock:
            if self._client:
                _LOGGER.debug(f"Closing existing client stack for {self._ble_device.address}.")
                try:
                    await self._client_stack.pop_all().aclose()
                except Exception as e:
                    _LOGGER.debug(f"Exception during client_stack.pop_all().aclose() in update_from_advertisement for {self._ble_device.address}: {e}", exc_info=True)
            self._client = None
            self._client_stack = AsyncExitStack()
            _LOGGER.debug(f"Client for {self._ble_device.address} reset due to new advertisement.")

# Custom exception classes (consider if IdealLedTimeout and IdealLedBleakError are still needed or if BleakError is sufficient)
# class IdealLedTimeout(BleakError):
#     """Custom timeout error."""
# class IdealLedBleakError(BleakError):
#     """Custom BleakError."""
