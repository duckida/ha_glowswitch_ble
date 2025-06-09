import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from bleak.exc import BleakError
from bleak.backends.device import BLEDevice

from custom_components.glowswitch.generic_bt_api.device import GenericBTDevice, _LOGGER

# A valid UUID string for testing
TEST_UUID = "00001101-0000-1000-8000-00805f9b34fb"
TEST_DATA = "aabbcc"

@pytest.mark.asyncio
async def test_write_gatt_retry_succeeds():
    """Test write_gatt when the first attempt fails with service discovery error, and retry succeeds."""
    mock_ble_device = MagicMock(spec=BLEDevice)
    mock_ble_device.address = "test_address"

    # Mock for the BleakClient instance
    mock_bleak_client_instance = AsyncMock(spec=BleakClient)
    mock_bleak_client_instance.write_gatt_char = AsyncMock(
        side_effect=[
            BleakError("Service Discovery has not been performed"), # First call fails
            None  # Second call succeeds
        ]
    )
    mock_bleak_client_instance.read_gatt_char = AsyncMock() # Add if get_client is called for other reasons

    # Mock for AsyncExitStack instance and its methods
    mock_aclose = AsyncMock()
    mock_pop_all_result = MagicMock()
    mock_pop_all_result.aclose = mock_aclose

    mock_async_exit_stack_instance = MagicMock(spec=AsyncExitStack)
    mock_async_exit_stack_instance.enter_async_context = AsyncMock(return_value=mock_bleak_client_instance)
    mock_async_exit_stack_instance.pop_all = MagicMock(return_value=mock_pop_all_result)

    # Patch BleakClient and AsyncExitStack in the module where GenericBTDevice uses them
    with patch('custom_components.glowswitch.generic_bt_api.device.BleakClient', return_value=mock_bleak_client_instance) as mock_bleak_client_class, \
         patch('custom_components.glowswitch.generic_bt_api.device.AsyncExitStack', return_value=mock_async_exit_stack_instance) as mock_async_exit_stack_class:

        device = GenericBTDevice(mock_ble_device)

        # Call the method under test
        await device.write_gatt(TEST_UUID, TEST_DATA)

        # Assertions
        # 1. get_client is called (first time, then by retry)
        # First call to get_client (initial attempt)
        mock_async_exit_stack_instance.enter_async_context.assert_any_call(mock_bleak_client_class(mock_ble_device, timeout=30))

        # Second call to get_client (after retry)
        # enter_async_context would be called again by the get_client in retry
        assert mock_async_exit_stack_instance.enter_async_context.call_count == 2

        # write_gatt_char called twice
        assert mock_bleak_client_instance.write_gatt_char.call_count == 2
        # Check arguments for write_gatt_char (optional, but good for completeness)
        expected_uuid = UUID("{" + TEST_UUID + "}")
        expected_data_bytes = bytearray.fromhex(TEST_DATA)
        mock_bleak_client_instance.write_gatt_char.assert_any_call(expected_uuid, expected_data_bytes, True)

        # pop_all().aclose() was called once for the disconnect
        mock_async_exit_stack_instance.pop_all.assert_called_once()
        mock_aclose.assert_called_once()

        # Verify BleakClient was instantiated twice (once initially, once on retry)
        assert mock_bleak_client_class.call_count == 2

@pytest.mark.asyncio
async def test_write_gatt_retry_fails():
    """Test write_gatt when the first attempt and retry both fail."""
    mock_ble_device = MagicMock(spec=BLEDevice)
    mock_ble_device.address = "test_address"

    mock_bleak_client_instance = AsyncMock(spec=BleakClient)
    mock_bleak_client_instance.write_gatt_char = AsyncMock(
        side_effect=[
            BleakError("Service Discovery has not been performed"), # First call
            BleakError("Another error after retry")  # Second call
        ]
    )

    mock_aclose = AsyncMock()
    mock_pop_all_result = MagicMock()
    mock_pop_all_result.aclose = mock_aclose

    mock_async_exit_stack_instance = MagicMock(spec=AsyncExitStack)
    mock_async_exit_stack_instance.enter_async_context = AsyncMock(return_value=mock_bleak_client_instance)
    mock_async_exit_stack_instance.pop_all = MagicMock(return_value=mock_pop_all_result)

    with patch('custom_components.glowswitch.generic_bt_api.device.BleakClient', return_value=mock_bleak_client_instance) as mock_bleak_client_class, \
         patch('custom_components.glowswitch.generic_bt_api.device.AsyncExitStack', return_value=mock_async_exit_stack_class):

        device = GenericBTDevice(mock_ble_device)

        with pytest.raises(BleakError, match="Another error after retry"):
            await device.write_gatt(TEST_UUID, TEST_DATA)

        # Assertions
        assert mock_async_exit_stack_instance.enter_async_context.call_count == 2
        assert mock_bleak_client_instance.write_gatt_char.call_count == 2

        expected_uuid = UUID("{" + TEST_UUID + "}")
        expected_data_bytes = bytearray.fromhex(TEST_DATA)
        mock_bleak_client_instance.write_gatt_char.assert_any_call(expected_uuid, expected_data_bytes, True)

        mock_async_exit_stack_instance.pop_all.assert_called_once()
        mock_aclose.assert_called_once()
        assert mock_bleak_client_class.call_count == 2

@pytest.mark.asyncio
async def test_write_gatt_other_bleak_error():
    """Test write_gatt when a BleakError not related to service discovery occurs."""
    mock_ble_device = MagicMock(spec=BLEDevice)
    mock_ble_device.address = "test_address"

    mock_bleak_client_instance = AsyncMock(spec=BleakClient)
    mock_bleak_client_instance.write_gatt_char = AsyncMock(
        side_effect=BleakError("Some other Bleak error")
    )

    mock_async_exit_stack_instance = MagicMock(spec=AsyncExitStack)
    mock_async_exit_stack_instance.enter_async_context = AsyncMock(return_value=mock_bleak_client_instance)
    # pop_all should not be called in this scenario
    mock_async_exit_stack_instance.pop_all = MagicMock()


    with patch('custom_components.glowswitch.generic_bt_api.device.BleakClient', return_value=mock_bleak_client_instance) as mock_bleak_client_class, \
         patch('custom_components.glowswitch.generic_bt_api.device.AsyncExitStack', return_value=mock_async_exit_stack_instance):

        device = GenericBTDevice(mock_ble_device)

        with pytest.raises(BleakError, match="Some other Bleak error"):
            await device.write_gatt(TEST_UUID, TEST_DATA)

        # Assertions
        # Client is fetched once
        mock_async_exit_stack_instance.enter_async_context.assert_called_once()
        # Write is attempted once
        mock_bleak_client_instance.write_gatt_char.assert_called_once()
        # Disconnect (pop_all) should NOT be called
        mock_async_exit_stack_instance.pop_all.assert_not_called()
        # BleakClient class called once
        mock_bleak_client_class.assert_called_once()

# Example of how to test logger calls (can be integrated into above tests)
@pytest.mark.asyncio
async def test_write_gatt_retry_succeeds_with_logging(caplog):
    """Test write_gatt retry success and checks for specific log messages."""
    # Setup mocks similar to test_write_gatt_retry_succeeds
    mock_ble_device = MagicMock(spec=BLEDevice)
    mock_ble_device.address = "test_address_logging"

    mock_bleak_client_instance = AsyncMock(spec=BleakClient)
    mock_bleak_client_instance.write_gatt_char = AsyncMock(
        side_effect=[
            BleakError("Service Discovery has not been performed"),
            None
        ]
    )
    # ... other mocks for AsyncExitStack ...
    mock_aclose = AsyncMock()
    mock_pop_all_result = MagicMock()
    mock_pop_all_result.aclose = mock_aclose

    mock_async_exit_stack_instance = MagicMock(spec=AsyncExitStack)
    mock_async_exit_stack_instance.enter_async_context = AsyncMock(return_value=mock_bleak_client_instance)
    mock_async_exit_stack_instance.pop_all = MagicMock(return_value=mock_pop_all_result)

    with patch('custom_components.glowswitch.generic_bt_api.device.BleakClient', return_value=mock_bleak_client_instance), \
         patch('custom_components.glowswitch.generic_bt_api.device.AsyncExitStack', return_value=mock_async_exit_stack_instance), \
         patch('custom_components.glowswitch.generic_bt_api.device._LOGGER') as mock_logger: # Patch logger

        device = GenericBTDevice(mock_ble_device)
        await device.write_gatt(TEST_UUID, TEST_DATA)

        # Assert logger calls
        # Example: Check if the specific error log for service discovery was called
        mock_logger.error.assert_any_call(
            "Service discovery error during write_gatt: %s. Reconnecting and retrying.",
            BleakError("Service Discovery has not been performed") # This needs to be the actual error instance or match via a custom matcher
        )
        # This specific check might be tricky due to the error instance comparison.
        # A more robust way for log checking might involve checking parts of the string.

        # Check that write_gatt_char was called twice
        assert mock_bleak_client_instance.write_gatt_char.call_count == 2
        # Check that pop_all().aclose() was called
        mock_async_exit_stack_instance.pop_all.assert_called_once()
        mock_aclose.assert_called_once()

# Note: For the logger test, directly comparing BleakError instances in assert_any_call might be flaky.
# It's often better to check `call_args` for string contents or use `caplog` fixture from pytest for more robust log testing.
# The provided logger test above uses mock_logger.error.assert_any_call, which has this caveat.
# Using caplog:
# import logging
# _LOGGER.propagate = True # if logs not showing up with caplog
# async def test_write_gatt_retry_succeeds_with_caplog(caplog):
#     caplog.set_level(logging.ERROR, logger="custom_components.glowswitch.generic_bt_api.device")
#     # ... rest of the test setup from test_write_gatt_retry_succeeds ...
#     await device.write_gatt(TEST_UUID, TEST_DATA)
#     assert "Service discovery error during write_gatt" in caplog.text
#     assert "Reconnecting and retrying" in caplog.text

# For now, I'll keep the logger test simpler and focus on the core logic tests.
# The `test_write_gatt_retry_succeeds_with_logging` is more of an advanced example.
# I will remove the direct logger assertion from the first two tests for simplicity and rely on the other assertions
# to confirm correct flow, which implies correct logging.
# The third test for "other bleak error" correctly asserts pop_all is NOT called.

# Corrected structure for the first two tests (removing direct mock_logger and focusing on behavior)

# (Re-pasting the first two tests here without direct logger assertion for clarity of what will be created)
# test_write_gatt_retry_succeeds would be:
# ... (setup as above)
#    with patch(...), patch(...):
#        device = GenericBTDevice(mock_ble_device)
#        await device.write_gatt(TEST_UUID, TEST_DATA)
#        assert mock_async_exit_stack_instance.enter_async_context.call_count == 2
#        assert mock_bleak_client_instance.write_gatt_char.call_count == 2
#        mock_async_exit_stack_instance.pop_all.assert_called_once()
#        mock_aclose.assert_called_once()
#        assert mock_bleak_client_class.call_count == 2

# test_write_gatt_retry_fails would be:
# ... (setup as above)
#    with patch(...), patch(...):
#        device = GenericBTDevice(mock_ble_device)
#        with pytest.raises(BleakError, match="Another error after retry"):
#            await device.write_gatt(TEST_UUID, TEST_DATA)
#        assert mock_async_exit_stack_instance.enter_async_context.call_count == 2
#        assert mock_bleak_client_instance.write_gatt_char.call_count == 2
#        mock_async_exit_stack_instance.pop_all.assert_called_once()
#        mock_aclose.assert_called_once()
#        assert mock_bleak_client_class.call_count == 2

# The final version of the file will include these three distinct tests:
# 1. test_write_gatt_retry_succeeds
# 2. test_write_gatt_retry_fails
# 3. test_write_gatt_other_bleak_error
# And a placeholder for the logging test if I decide to refine it later, or use caplog.
# For now, I'll include the three core logic tests.

# The provided code block will contain the refined versions of these tests.
# I've also decided to patch `_LOGGER` within `device.py` to check for the specific error message.
# This is a bit more direct than `caplog` for this specific case, but `caplog` is generally more robust.
# The patch for `_LOGGER` is added to the test cases.
# The `test_write_gatt_retry_succeeds_with_logging` is removed to avoid redundancy if other tests check logging.
# I will add logger checks to the first two tests.

# Final plan for the file content:
# - Imports
# - Constants TEST_UUID, TEST_DATA
# - test_write_gatt_retry_succeeds (with logger check)
# - test_write_gatt_retry_fails (with logger check)
# - test_write_gatt_other_bleak_error (checks pop_all not called, no specific error log needed here beyond what Bleak/pytest does)

# One detail: `mock_bleak_client_class(mock_ble_device, timeout=30)` in `assert_any_call`
# The `BleakClient` is instantiated within `get_client`. The patched `BleakClient` class itself is what we
# are checking the call against. So it should be `mock_bleak_client_class` not `mock_bleak_client_instance`.
# And `BleakClient` (the class) is called, then it returns `mock_bleak_client_instance`.
# So the assertion `mock_async_exit_stack_instance.enter_async_context.assert_any_call(mock_bleak_client_class(mock_ble_device, timeout=30))`
# is incorrect. `enter_async_context` is called with the *instance* that `BleakClient()` returns.
# The `BleakClient` *class* is patched to return `mock_bleak_client_instance`.
# So `mock_async_exit_stack_instance.enter_async_context.assert_any_call(mock_bleak_client_instance)` is more appropriate.
# And `mock_bleak_client_class.assert_any_call(mock_ble_device, timeout=30)` to check how the client was created.

# Corrected assertions for client creation and usage:
# - `mock_bleak_client_class.assert_any_call(mock_ble_device, timeout=30)` (checks BleakClient constructor call)
# - `mock_async_exit_stack_instance.enter_async_context.assert_any_call(mock_bleak_client_instance)` (checks what's passed to stack)

# Let's refine the code block.I've thought through the test cases and the necessary mocks. I will create the `custom_components/glowswitch/tests/test_device.py` file with three main test scenarios for `write_gatt`:
1.  **Retry Succeeds**: First `write_gatt_char` call fails with a "Service Discovery" `BleakError`, the device reconnects, and the second call succeeds. Logger calls will also be checked.
2.  **Retry Fails**: First call fails similarly, but the second call (after reconnect) also fails with a different `BleakError`, which should then be re-raised. Logger calls for the initial error will be checked.
3.  **Other Bleak Error**: `write_gatt_char` fails immediately with a `BleakError` not related to service discovery. This error should be re-raised without a retry attempt.

I will use `unittest.mock.patch` to mock `BleakClient`, `AsyncExitStack`, and the `_LOGGER` instance within the `device.py` module.

Here is the content of the new test file:
