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

    def poll_needed(self, seconds_since_last_poll: float | None) -> bool:
        # For now, always return True to ensure regular polling.
        # This can be refined later if needed.
        _LOGGER.debug(f"Poll needed for {self._ble_device.address}? True (seconds_since_last_poll: {seconds_since_last_poll})")
        return True

    async def update(self):
        _LOGGER.debug(f"Attempting to update {self._ble_device.address}")
        try:
            client = await self.get_client()
            if not client:
                _LOGGER.warning(f"Cannot update {self._ble_device.address}: no client available after get_client.")
                return

            if not client.is_connected:
                _LOGGER.warning(f"Cannot update {self._ble_device.address}: client not connected.")
                # Attempt to reconnect explicitly if get_client didn't throw or already reconnected.
                # This might be redundant if get_client is robust enough.
                client = await self.get_client() # Try one more time
                if not client or not client.is_connected:
                    _LOGGER.error(f"Failed to connect to {self._ble_device.address} for update.")
                    return

            _LOGGER.debug(f"Polling update for {self._ble_device.address}. Client connected: {client.is_connected}")
            # Placeholder for a benign read operation to keep the connection alive.
            # For example, reading a common characteristic like "Device Name" (UUID 00002a00-0000-1000-8000-00805f9b34fb)
            # device_name_uuid = "00002a00-0000-1000-8000-00805f9b34fb"
            # try:
            #     device_name = await client.read_gatt_char(device_name_uuid)
            #     _LOGGER.debug(f"Successfully read device name for {self._ble_device.address}: {bytes(device_name).decode('utf-8', errors='replace')}")
            # except BleakError as e:
            #     _LOGGER.warning(f"Could not perform keep-alive read for {self._ble_device.address}: {e}")
            # except Exception as e:
            #     _LOGGER.error(f"Unexpected error during keep-alive read for {self._ble_device.address}: {e}")
            
            # For now, just log that the update poll happened.
            # If a specific read is not necessary for keep-alive for this device, this is sufficient.
            _LOGGER.info(f"Update poll executed for {self._ble_device.address}. Device should be connected.")

        except BleakError as e:
            _LOGGER.warning(f"BleakError during update for {self._ble_device.address}: {e}")
        except Exception as e:
            _LOGGER.error(f"Unexpected error during update for {self._ble_device.address}: {e}", exc_info=True)

    async def stop(self):
        _LOGGER.debug(f"Stopping connection to {self._ble_device.address}")
        if self._client and self._client.is_connected:
            try:
                await self._client.disconnect()
                _LOGGER.debug(f"Successfully disconnected from {self._ble_device.address}")
            except BleakError as e:
                _LOGGER.warning(f"Error disconnecting from {self._ble_device.address}: {e}")
        await self._client_stack.pop_all().aclose()
        self._client = None
        _LOGGER.debug(f"Connection stack closed for {self._ble_device.address}")


    @property
    def connected(self):
        return self._client is not None and self._client.is_connected

    async def get_client(self):
        async with self._lock:
            # Check if client exists and is connected
            if self._client and self._client.is_connected:
                _LOGGER.debug(f"Connection to {self._ble_device.address} already established.")
                return self._client

            # Attempt to connect or reconnect
            _LOGGER.debug(f"Attempting to connect to {self._ble_device.address}")
            try:
                # If client exists but is not connected, ensure it's cleaned up from stack
                if self._client:
                    _LOGGER.debug(f"Cleaning up previous disconnected client for {self._ble_device.address}")
                    # await self._client_stack.pop_all().aclose() # This might be too aggressive if other contexts use the stack
                                                              # Instead, BleakClient handles its own disconnection on exit.
                                                              # The stack will call __aexit__ on the client instance.
                    pass # BleakClient's __aexit__ should handle disconnection if it was entered into stack

                new_client = BleakClient(self._ble_device, timeout=30)
                self._client = await self._client_stack.enter_async_context(new_client)
                _LOGGER.debug(f"Successfully connected to {self._ble_device.address}. Client: {self._client}")

                # Verify connection status after attempting to connect
                if not self._client.is_connected:
                    _LOGGER.warning(f"Client for {self._ble_device.address} not connected after connection attempt.")
                    # This indicates an issue, possibly need to raise an error or handle retry
                    raise BleakError(f"Failed to establish connection with {self._ble_device.address}")

            except asyncio.TimeoutError as exc:
                _LOGGER.warning(f"Timeout on connect to {self._ble_device.address}: {exc}")
                await self._client_stack.pop_all().aclose() # Clean up stack on timeout
                self._client = None # Ensure client is None on failure
                raise BleakError(f"Timeout on connect to {self._ble_device.address}") from exc
            except BleakError as exc:
                _LOGGER.error(f"BleakError on connect to {self._ble_device.address}: {exc}")
                await self._client_stack.pop_all().aclose() # Clean up stack on BleakError
                self._client = None # Ensure client is None on failure
                raise
            except Exception as exc:
                _LOGGER.error(f"Unexpected error connecting to {self._ble_device.address}: {exc}", exc_info=True)
                await self._client_stack.pop_all().aclose() # Clean up on any other error
                self._client = None
                raise BleakError(f"Unexpected error connecting to {self._ble_device.address}: {exc}") from exc
        
        if not self._client:
             _LOGGER.error(f"Failed to get client for {self._ble_device.address}, client is None.")
             raise BleakError(f"Failed to get client for {self._ble_device.address}")
        
        return self._client


    async def write_gatt(self, target_uuid, data):
        client = await self.get_client() 
        if not client:
            _LOGGER.error(f"Cannot write GATT {target_uuid} for {self._ble_device.address}: no client.")
            raise BleakError(f"No client for write GATT {target_uuid} on {self._ble_device.address}")
        # uuid_str = "{" + target_uuid + "}" # UUIDs should be valid format
        uuid = UUID(target_uuid)
        data_as_bytes = bytearray.fromhex(data)
        _LOGGER.debug(f"Writing GATT {target_uuid} for {self._ble_device.address}: {data}")
        await client.write_gatt_char(uuid, data_as_bytes, True)

    async def read_gatt(self, target_uuid):
        client = await self.get_client() 
        if not client:
            _LOGGER.error(f"Cannot read GATT {target_uuid} for {self._ble_device.address}: no client.")
            raise BleakError(f"No client for read GATT {target_uuid} on {self._ble_device.address}")
        # uuid_str = "{" + target_uuid + "}"
        uuid = UUID(target_uuid)
        _LOGGER.debug(f"Reading GATT {target_uuid} for {self._ble_device.address}")
        data = await client.read_gatt_char(uuid)
        _LOGGER.debug(f"Read GATT {target_uuid} for {self._ble_device.address} successful: {data}")
        return data

    def update_from_advertisement(self, advertisement):
        _LOGGER.debug(f"Device {self._ble_device.address} updated from advertisement: {advertisement.local_name}") # Log something more specific
        pass
