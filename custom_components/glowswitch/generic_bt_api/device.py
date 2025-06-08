"""generic bt device"""

from uuid import UUID
import asyncio
import logging
from contextlib import AsyncExitStack

from bleak import BleakClient
from bleak.exc import BleakError

_LOGGER = logging.getLogger(__name__)

RETRY_ATTEMPTS = 2
# Custom exceptions (if still needed, otherwise rely on BleakError)
# For now, assuming they might be raised by get_client as per original snippet
class IdealLedTimeout(Exception):
    pass
class IdealLedBleakError(Exception):
    pass

class GenericBTDevice:
    """Generic BT Device Class"""
    def __init__(self, ble_device):
        self._ble_device = ble_device
        self._client: BleakClient | None = None
        self._client_stack = AsyncExitStack()
        self._lock = asyncio.Lock() # Lock for connection management

    async def update(self):
        """Placeholder for updates if needed."""
        pass

    async def stop(self):
        """Stop the device and disconnect."""
        _LOGGER.debug("Stopping device %s and disconnecting client.", self._ble_device.address)
        async with self._lock: # Ensure exclusive access for disconnect
            await self.disconnect()

    async def disconnect(self):
        """Disconnects and cleans up the Bleak client and its context stack.
        This method assumes it might be called while the lock is already held.
        """
        _LOGGER.debug("Disconnecting client for %s.", self._ble_device.address)
        if self._client:
            try:
                if self._client.is_connected:
                    await self._client.disconnect()
            except BleakError as e:
                _LOGGER.debug(f"BleakError during explicit disconnect for {self._ble_device.address}: {e}")
            except Exception as e: # Catch any other potential error during disconnect
                _LOGGER.debug(f"Unexpected error during explicit disconnect for {self._ble_device.address}: {e}")
            finally:
                self._client = None # Crucial to mark client as None

        # Reset the BleakClient context stack
        # This ensures that even if client disconnect failed, the stack is fresh
        if hasattr(self, '_client_stack'): # Ensure _client_stack exists
             await self._client_stack.pop_all().aclose() # Pop all contexts (should be at most one)

        self._client_stack = AsyncExitStack() # Reinitialize for next connection
        _LOGGER.debug("Client for %s disconnected and stack reset.", self._ble_device.address)

    @property
    def connected(self) -> bool:
        """Check if the client is connected."""
        return self._client is not None and self._client.is_connected

    async def get_client(self) -> BleakClient:
        """Get a connected BleakClient instance."""
        async with self._lock:
            if self._client and self._client.is_connected:
                _LOGGER.debug("Connection reused for %s", self._ble_device.address)
                return self._client

            # If client exists but not connected, or doesn't exist
            if self._client: # It exists but not connected
                _LOGGER.debug("Client for %s exists but not connected. Cleaning up.", self._ble_device.address)
                # Call internal disconnect without lock, as lock is already held.
                await self.disconnect() # This will set self._client to None and reset stack

            _LOGGER.debug("Attempting to connect to %s", self._ble_device.address)
            try:
                # self._client_stack should be fresh here due to disconnect logic
                self._client = await self._client_stack.enter_async_context(
                    BleakClient(self._ble_device, timeout=30.0) # Using float for timeout
                )
                if not self._client.is_connected: # Should not happen if BleakClient constructor succeeds
                    _LOGGER.error("Connection to %s failed immediately after connect call.", self._ble_device.address)
                    await self.disconnect() # Cleanup
                    raise IdealLedBleakError(f"Failed to connect to {self._ble_device.address}")
                _LOGGER.debug("Successfully connected to %s", self._ble_device.address)
                return self._client
            except asyncio.TimeoutError as exc:
                _LOGGER.warning("Timeout on connect to %s: %s", self._ble_device.address, exc)
                await self.disconnect() # Ensure cleanup on timeout
                raise IdealLedTimeout(f"Timeout on connect to {self._ble_device.address}") from exc
            except BleakError as exc:
                _LOGGER.warning("BleakError on connect to %s: %s", self._ble_device.address, exc)
                await self.disconnect() # Ensure cleanup on BleakError
                raise IdealLedBleakError(f"BleakError on connect to {self._ble_device.address}") from exc
            except Exception as exc: # Catch any other unexpected error during connection
                _LOGGER.error("Unexpected error on connect to %s: %s", self._ble_device.address, exc, exc_info=True)
                await self.disconnect()
                raise IdealLedBleakError(f"Unexpected error connecting to {self._ble_device.address}") from exc


    async def write_gatt(self, target_uuid_str: str, data: str):
        """Write data to a GATT characteristic with retry."""
        # UUID parsing should handle strings with or without braces
        try:
            target_uuid = UUID(target_uuid_str.replace("{","").replace("}",""))
        except ValueError:
            _LOGGER.error("Invalid UUID format: %s", target_uuid_str)
            raise

        data_as_bytes = bytearray.fromhex(data)
        last_exception = None

        for attempt in range(RETRY_ATTEMPTS):
            try:
                client = await self.get_client() # Ensures client is connected or raises
                _LOGGER.debug("Attempting GATT write to %s for %s, data: '%s', attempt %s/%s", target_uuid, self._ble_device.address, data, attempt + 1, RETRY_ATTEMPTS)
                await client.write_gatt_char(target_uuid, data_as_bytes, response=True)
                _LOGGER.debug("Successfully wrote to %s for %s", target_uuid, self._ble_device.address)
                return # Success
            except (IdealLedTimeout, IdealLedBleakError) as e: # Errors from get_client()
                _LOGGER.warning("Connection error during write attempt %s/%s for %s: %s", attempt + 1, RETRY_ATTEMPTS, self._ble_device.address, e)
                last_exception = e
                # No disconnect here as get_client's exception handlers should have called it.
                if attempt >= RETRY_ATTEMPTS - 1: # Last attempt
                    _LOGGER.error("Failed to connect for GATT write to %s for %s after %s attempts.", target_uuid, self._ble_device.address, RETRY_ATTEMPTS)
                    raise
                # If get_client fails, it might be a more persistent issue, short sleep before retry
                await asyncio.sleep(0.5 if attempt < 1 else 1.0) # Slightly longer sleep for subsequent retries
            except BleakError as e: # Errors from write_gatt_char itself
                _LOGGER.warning("BleakError during GATT write to %s for %s (Attempt %s/%s): %s", target_uuid, self._ble_device.address, attempt + 1, RETRY_ATTEMPTS, e)
                last_exception = e
                async with self._lock: # Ensure lock is acquired before calling disconnect
                    await self.disconnect()
                if attempt < RETRY_ATTEMPTS - 1:
                    await asyncio.sleep(0.5 if attempt < 1 else 1.0)
                else: # Last attempt
                    _LOGGER.error("Failed to write to %s for %s after %s attempts.", target_uuid, self._ble_device.address, RETRY_ATTEMPTS)
                    raise # Re-raise the last BleakError

        # Fallback if loop completes unexpectedly (should be covered by raises)
        if last_exception:
            raise last_exception


    async def read_gatt(self, target_uuid_str: str) -> bytearray:
        """Read data from a GATT characteristic with retry."""
        try:
            target_uuid = UUID(target_uuid_str.replace("{","").replace("}",""))
        except ValueError:
            _LOGGER.error("Invalid UUID format: %s", target_uuid_str)
            raise

        last_exception = None

        for attempt in range(RETRY_ATTEMPTS):
            try:
                client = await self.get_client() # Ensures client is connected or raises
                _LOGGER.debug("Attempting GATT read from %s for %s, attempt %s/%s", target_uuid, self._ble_device.address, attempt + 1, RETRY_ATTEMPTS)
                value = await client.read_gatt_char(target_uuid)
                _LOGGER.debug("Successfully read from %s for %s: %s", target_uuid, self._ble_device.address, value)
                return value # Success
            except (IdealLedTimeout, IdealLedBleakError) as e: # Errors from get_client()
                _LOGGER.warning("Connection error during read attempt %s/%s for %s: %s", attempt + 1, RETRY_ATTEMPTS, self._ble_device.address, e)
                last_exception = e
                if attempt >= RETRY_ATTEMPTS - 1:
                    _LOGGER.error("Failed to connect for GATT read from %s for %s after %s attempts.", target_uuid, self._ble_device.address, RETRY_ATTEMPTS)
                    raise
                await asyncio.sleep(0.5 if attempt < 1 else 1.0)
            except BleakError as e: # Errors from read_gatt_char itself
                _LOGGER.warning("BleakError during GATT read from %s for %s (Attempt %s/%s): %s", target_uuid, self._ble_device.address, attempt + 1, RETRY_ATTEMPTS, e)
                last_exception = e
                async with self._lock: # Ensure lock is acquired before calling disconnect
                    await self.disconnect()
                if attempt < RETRY_ATTEMPTS - 1:
                    await asyncio.sleep(0.5 if attempt < 1 else 1.0)
                else: # Last attempt
                    _LOGGER.error("Failed to read from %s for %s after %s attempts.", target_uuid, self._ble_device.address, RETRY_ATTEMPTS)
                    raise # Re-raise the last BleakError

        if last_exception: # Fallback
            raise last_exception

    def update_from_advertisement(self, advertisement):
        """Placeholder for updates from advertisement data if needed."""
        pass
