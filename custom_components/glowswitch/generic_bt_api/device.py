"""generic bt device"""

from uuid import UUID
import asyncio
import logging
from contextlib import AsyncExitStack

from bleak import BleakClient
from bleak.exc import BleakError

# Custom Exceptions
class IdealLedTimeout(Exception):
    """Custom timeout exception for Ideal LED operations."""
    pass

class IdealLedBleakError(BleakError):
    """Custom BleakError wrapper for Ideal LED operations."""
    pass

_LOGGER = logging.getLogger(__name__)


class GenericBTDevice:
    """Generic BT Device Class"""
    # Constants for retry mechanism
    MAX_SERVICE_DISCOVERY_RETRIES = 3
    SERVICE_DISCOVERY_RETRY_DELAY = 15  # seconds

    def __init__(self, ble_device):
        self._ble_device = ble_device
        self._client: BleakClient | None = None
        self._client_stack = AsyncExitStack()
        self._lock = asyncio.Lock()

    async def update(self):
        pass

    async def stop(self):
            pass

    @property
    def connected(self):
        return not self._client is None

    async def get_client(self):
        async with self._lock:
            if not self._client:
                _LOGGER.debug("Connecting")
                try:
                    self._client = await self._client_stack.enter_async_context(BleakClient(self._ble_device, timeout=30))
                    _LOGGER.debug("Successfully connected to device %s", self._ble_device.address)
                except asyncio.TimeoutError as exc:
                    _LOGGER.debug("Timeout on connect", exc_info=True)
                    self._client = None # Ensure client is None on timeout
                    raise IdealLedTimeout("Timeout on connect") from exc
                except BleakError as exc:
                    _LOGGER.debug("Error on connect", exc_info=True)
                    self._client = None # Ensure client is None on BleakError
                    raise IdealLedBleakError("Error on connect") from exc
            else:
                _LOGGER.debug("Connection reused")

    async def write_gatt(self, target_uuid, data):
        # Initial connection attempt is made here. If get_client() fails, it will raise an exception.
        await self.get_client()

        if not self._client: # Should not happen if get_client succeeded without error and self._lock works
            _LOGGER.error("Client not available for GATT write after get_client call for %s. This should not happen.", self._ble_device.address)
            # Attempt to force a reconnect by clearing the client, then try get_client again.
            # This is an edge case recovery.
            self._client = None
            await self._client_stack.pop_all().aclose() # Ensure stack is clean before next get_client
            await self.get_client()
            if not self._client: # If still no client, raise an error.
                 raise IdealLedBleakError(f"Failed to establish client connection for {self._ble_device.address} before GATT write.")


        uuid_str = "{" + target_uuid + "}"
        uuid = UUID(uuid_str)
        data_as_bytes = bytearray.fromhex(data)

        try:
            await self._client.write_gatt_char(uuid, data_as_bytes, True)
        except BleakError as e:
            if "Service Discovery has not been performed" in str(e):
                _LOGGER.warning(
                    "Service discovery error for %s during GATT write. Attempting up to %s retries with %s sec delay. Initial error: %s",
                    self._ble_device.address,
                    self.MAX_SERVICE_DISCOVERY_RETRIES,
                    self.SERVICE_DISCOVERY_RETRY_DELAY,
                    e
                )
                last_exception = e

                for attempt in range(self.MAX_SERVICE_DISCOVERY_RETRIES):
                    _LOGGER.info(
                        "Retry attempt %s/%s for %s after %s sec delay...",
                        attempt + 1,
                        self.MAX_SERVICE_DISCOVERY_RETRIES,
                        self._ble_device.address,
                        self.SERVICE_DISCOVERY_RETRY_DELAY
                    )
                    await asyncio.sleep(self.SERVICE_DISCOVERY_RETRY_DELAY)

                    # Clean up previous client state for a fresh connection attempt
                    await self._client_stack.pop_all().aclose() # Close and remove client from stack
                    self._client = None # Ensure client is None before get_client

                    try:
                        _LOGGER.debug("Attempting reconnect for retry %s for device %s...", attempt + 1, self._ble_device.address)
                        await self.get_client() # This will attempt to connect and set self._client
                        if not self._client: # Defensive check
                             _LOGGER.error("Reconnect attempt %s for %s resulted in no client. Skipping GATT write attempt.", attempt + 1, self._ble_device.address)
                             # Store an appropriate exception or re-use last_exception if that's more fitting
                             last_exception = IdealLedBleakError(f"Failed to re-establish client for {self._ble_device.address} on retry {attempt + 1}")
                             continue # Go to next retry attempt

                        _LOGGER.debug("Reconnected for retry %s for %s. Attempting GATT write.", attempt + 1, self._ble_device.address)
                        await self._client.write_gatt_char(uuid, data_as_bytes, True)
                        _LOGGER.info("GATT write successful on retry %s/%s for %s.",
                                     attempt + 1, self.MAX_SERVICE_DISCOVERY_RETRIES, self._ble_device.address)
                        return  # Operation succeeded, exit write_gatt

                    except Exception as retry_exc: # Catches BleakError from write_gatt_char or errors from get_client (IdealLedTimeout, IdealLedBleakError)
                        _LOGGER.warning(
                            "Retry attempt %s/%s failed for %s: %s",
                            attempt + 1,
                            self.MAX_SERVICE_DISCOVERY_RETRIES,
                            self._ble_device.address,
                            retry_exc
                        )
                        last_exception = retry_exc

                # If loop completes, all retries failed
                _LOGGER.error(
                    "All %s retry attempts failed for GATT write to %s. Last error: %s",
                    self.MAX_SERVICE_DISCOVERY_RETRIES,
                    self._ble_device.address,
                    last_exception
                )
                raise last_exception # Raise the last encountered exception
            else:
                # Not a service discovery error, re-raise immediately
                raise e
        # Note: Other exceptions (non-BleakError) from the initial write_gatt_char are not caught here and will propagate.

    async def read_gatt(self, target_uuid):
        await self.get_client()
        uuid_str = "{" + target_uuid + "}"
        uuid = UUID(uuid_str)
        data = await self._client.read_gatt_char(uuid)
        print(data)
        return data

    def update_from_advertisement(self, advertisement):
        pass
