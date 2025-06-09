import pytest
import asyncio # Ensure asyncio is imported for patching sleep
from unittest.mock import AsyncMock, MagicMock, patch, call # call for checking sequence of log calls
from uuid import UUID

from bleak.exc import BleakError
from bleak.backends.device import BLEDevice

from custom_components.glowswitch.generic_bt_api.device import (
    GenericBTDevice,
    _LOGGER, # Keep for direct assertion if needed, though MockLogger from patch is primary
    IdealLedTimeout,
    IdealLedBleakError # Import if used by tests
)

# Constants for tests
TEST_UUID_STR = "00001101-0000-1000-8000-00805f9b34fb"
TEST_DATA_HEX = "aabbcc"
SERVICE_DISCOVERY_ERROR_MSG = "Service Discovery has not been performed"

# Helper to create a standard BLEDevice mock
def create_mock_ble_device(address="test_address"):
    dev = MagicMock(spec=BLEDevice)
    dev.address = address
    return dev

# Helper to create a mock BleakClient instance
def create_mock_bleak_client_instance():
    client = AsyncMock(spec=BleakClient)
    client.name = "mock_bleak_client_instance"
    return client

# Helper to create a mock AsyncExitStack
def create_mock_async_exit_stack(client_to_return):
    stack = MagicMock(spec=AsyncExitStack)
    stack.enter_async_context = AsyncMock(return_value=client_to_return)
    aclose_mock = AsyncMock()
    pop_all_mock = MagicMock()
    pop_all_mock.aclose = aclose_mock
    stack.pop_all = MagicMock(return_value=pop_all_mock)
    return stack, aclose_mock

@pytest.mark.asyncio
async def test_write_gatt_no_error_succeeds_first_try():
    """1. Test GATT write success on the first attempt without any errors."""
    mock_ble_device = create_mock_ble_device()
    ble_client_mock = create_mock_bleak_client_instance()
    ble_client_mock.write_gatt_char = AsyncMock(return_value=None) # Success

    exit_stack_mock, _ = create_mock_async_exit_stack(ble_client_mock)

    with patch('custom_components.glowswitch.generic_bt_api.device.BleakClient', return_value=ble_client_mock) as PatchedBleakClient, \
         patch('custom_components.glowswitch.generic_bt_api.device.AsyncExitStack', return_value=exit_stack_mock), \
         patch('custom_components.glowswitch.generic_bt_api.device._LOGGER') as MockLogger, \
         patch('asyncio.sleep', new_callable=AsyncMock) as MockSleep:

        device = GenericBTDevice(mock_ble_device)
        await device.write_gatt(TEST_UUID_STR, TEST_DATA_HEX)

        PatchedBleakClient.assert_called_once_with(mock_ble_device, timeout=30)
        ble_client_mock.write_gatt_char.assert_called_once()
        MockSleep.assert_not_called() # No retries, so no sleep

        # Check that no retry-related logs were made
        for log_call in MockLogger.warning.call_args_list + MockLogger.info.call_args_list:
            assert "retry" not in log_call.args[0].lower()
            assert "service discovery" not in log_call.args[0].lower()

@pytest.mark.asyncio
async def test_write_gatt_service_discovery_succeeds_first_retry():
    """2. Service discovery error, then success on 1st retry attempt."""
    mock_ble_device = create_mock_ble_device()

    client_try1 = create_mock_bleak_client_instance()
    client_try1.write_gatt_char = AsyncMock(side_effect=BleakError(SERVICE_DISCOVERY_ERROR_MSG))

    client_try2 = create_mock_bleak_client_instance()
    client_try2.write_gatt_char = AsyncMock(return_value=None) # Success on retry

    # BleakClient constructor will be called twice
    PatchedBleakClient_side_effect = [client_try1, client_try2]

    exit_stack_mock, aclose_mock = create_mock_async_exit_stack(client_try1) # Initial stack setup
    # enter_async_context will be called again for the second client
    exit_stack_mock.enter_async_context.side_effect = [client_try1, client_try2]


    with patch('custom_components.glowswitch.generic_bt_api.device.BleakClient', side_effect=PatchedBleakClient_side_effect) as PatchedBleakClient, \
         patch('custom_components.glowswitch.generic_bt_api.device.AsyncExitStack', return_value=exit_stack_mock), \
         patch('custom_components.glowswitch.generic_bt_api.device._LOGGER') as MockLogger, \
         patch('asyncio.sleep', new_callable=AsyncMock) as MockSleep:

        device = GenericBTDevice(mock_ble_device)
        await device.write_gatt(TEST_UUID_STR, TEST_DATA_HEX)

        assert PatchedBleakClient.call_count == 2 # Initial + 1 retry
        assert exit_stack_mock.enter_async_context.call_count == 2
        assert client_try1.write_gatt_char.call_count == 1 # First attempt
        assert client_try2.write_gatt_char.call_count == 1 # Retry attempt

        MockSleep.assert_called_once_with(GenericBTDevice.SERVICE_DISCOVERY_RETRY_DELAY)
        aclose_mock.assert_called_once() # From the cleanup before retry

        # Log checks
        assert MockLogger.warning.call_args_list[0].args[0].startswith("Service discovery error for %s during GATT write.")
        assert MockLogger.info.call_args_list[0].args[0].startswith("Retry attempt 1/%s for %s after %s sec delay...")
        assert MockLogger.debug.call_args_list[2].args[0].startswith("Attempting reconnect for retry 1...") # 0,1 are initial connect
        assert MockLogger.debug.call_args_list[3].args[0].startswith("Reconnected for retry 1.")
        assert MockLogger.info.call_args_list[1].args[0].startswith("GATT write successful on retry 1/%s for %s.")


@pytest.mark.asyncio
async def test_write_gatt_service_discovery_succeeds_last_retry():
    """3. Service discovery error, success on the last possible retry attempt."""
    mock_ble_device = create_mock_ble_device()
    max_retries = GenericBTDevice.MAX_SERVICE_DISCOVERY_RETRIES

    # Initial client fails with service discovery
    initial_client = create_mock_bleak_client_instance()
    initial_client.write_gatt_char = AsyncMock(side_effect=BleakError(SERVICE_DISCOVERY_ERROR_MSG))

    # Subsequent retry clients also fail, except the last one
    retry_clients_effects = []
    # All but the last retry attempt's write_gatt_char will fail
    for i in range(max_retries - 1):
        client = create_mock_bleak_client_instance()
        client.write_gatt_char = AsyncMock(side_effect=BleakError(f"Some other error on retry {i+1}"))
        retry_clients_effects.append(client)

    # Last retry client succeeds
    last_retry_client = create_mock_bleak_client_instance()
    last_retry_client.write_gatt_char = AsyncMock(return_value=None)
    retry_clients_effects.append(last_retry_client)

    PatchedBleakClient_side_effect = [initial_client] + retry_clients_effects

    exit_stack_mock, aclose_mock = create_mock_async_exit_stack(None)
    exit_stack_mock.enter_async_context.side_effect = PatchedBleakClient_side_effect


    with patch('custom_components.glowswitch.generic_bt_api.device.BleakClient', side_effect=PatchedBleakClient_side_effect) as PatchedBleakClient, \
         patch('custom_components.glowswitch.generic_bt_api.device.AsyncExitStack', return_value=exit_stack_mock), \
         patch('custom_components.glowswitch.generic_bt_api.device._LOGGER') as MockLogger, \
         patch('asyncio.sleep', new_callable=AsyncMock) as MockSleep:

        device = GenericBTDevice(mock_ble_device)
        await device.write_gatt(TEST_UUID_STR, TEST_DATA_HEX)

        assert PatchedBleakClient.call_count == 1 + max_retries
        assert initial_client.write_gatt_char.call_count == 1
        for i in range(max_retries):
            assert retry_clients_effects[i].write_gatt_char.call_count == 1

        assert MockSleep.call_count == max_retries
        assert aclose_mock.call_count == max_retries

        # Check final success log
        success_log_found = any(
            f"GATT write successful on retry {max_retries}/{max_retries}" in log_call.args[0]
            for log_call in MockLogger.info.call_args_list
        )
        assert success_log_found


@pytest.mark.asyncio
async def test_write_gatt_service_discovery_all_retries_fail_write():
    """4. Service discovery error, all retry attempts fail (persistent write_gatt_char failure)."""
    mock_ble_device = create_mock_ble_device()
    max_retries = GenericBTDevice.MAX_SERVICE_DISCOVERY_RETRIES
    final_error_msg = "Persistent error on last retry write"

    initial_client = create_mock_bleak_client_instance()
    initial_client.write_gatt_char = AsyncMock(side_effect=BleakError(SERVICE_DISCOVERY_ERROR_MSG))

    retry_clients_effects = []
    for i in range(max_retries -1): # All but last fail with generic error
        client = create_mock_bleak_client_instance()
        client.write_gatt_char = AsyncMock(side_effect=BleakError(f"Write error on retry {i+1}"))
        retry_clients_effects.append(client)

    last_retry_client = create_mock_bleak_client_instance() # Last one also fails
    last_retry_client.write_gatt_char = AsyncMock(side_effect=BleakError(final_error_msg))
    retry_clients_effects.append(last_retry_client)

    PatchedBleakClient_side_effect = [initial_client] + retry_clients_effects

    exit_stack_mock, aclose_mock = create_mock_async_exit_stack(None)
    exit_stack_mock.enter_async_context.side_effect = PatchedBleakClient_side_effect

    with patch('custom_components.glowswitch.generic_bt_api.device.BleakClient', side_effect=PatchedBleakClient_side_effect) as PatchedBleakClient, \
         patch('custom_components.glowswitch.generic_bt_api.device.AsyncExitStack', return_value=exit_stack_mock), \
         patch('custom_components.glowswitch.generic_bt_api.device._LOGGER') as MockLogger, \
         patch('asyncio.sleep', new_callable=AsyncMock) as MockSleep:

        device = GenericBTDevice(mock_ble_device)
        with pytest.raises(BleakError, match=final_error_msg):
            await device.write_gatt(TEST_UUID_STR, TEST_DATA_HEX)

        assert PatchedBleakClient.call_count == 1 + max_retries
        assert initial_client.write_gatt_char.call_count == 1
        for client in retry_clients_effects:
            assert client.write_gatt_char.call_count == 1

        assert MockSleep.call_count == max_retries
        assert MockLogger.error.call_args_list[-1].args[0].startswith(f"All {max_retries} retry attempts failed for GATT write")


@pytest.mark.asyncio
async def test_write_gatt_service_discovery_get_client_fails_last_retry():
    """5. Service discovery error, get_client() fails during the last retry attempt."""
    mock_ble_device = create_mock_ble_device()
    max_retries = GenericBTDevice.MAX_SERVICE_DISCOVERY_RETRIES
    reconnect_fail_error_msg = "Timeout on connect" # Match IdealLedTimeout message

    initial_client = create_mock_bleak_client_instance()
    initial_client.write_gatt_char = AsyncMock(side_effect=BleakError(SERVICE_DISCOVERY_ERROR_MSG))

    # All retry attempts will involve a BleakClient that successfully constructs,
    # but the *last* attempt's get_client call will fail internally due to BleakClient constructor raising an error.
    bleak_client_constructor_side_effects = [initial_client] # First connect
    for _ in range(max_retries -1 ): # Successful reconnects for earlier retries
         bleak_client_constructor_side_effects.append(create_mock_bleak_client_instance())
    # Last retry's BleakClient constructor will fail leading to IdealLedTimeout from get_client
    bleak_client_constructor_side_effects.append(asyncio.TimeoutError("Simulated get_client timeout on last retry"))

    # write_gatt_char behavior for clients that do connect during retries (all but the last)
    # The clients from bleak_client_constructor_side_effects[1] to bleak_client_constructor_side_effects[-2]
    # need their write_gatt_char mocked to also fail, to ensure the loop continues to the last failing get_client.
    # This setup is getting complex. Let's simplify: get_client fails on the *first* retry.

    # Simplified: get_client fails on the first retry attempt.
    # Test if the loop runs MAX_SERVICE_DISCOVERY_RETRIES times and then raises the error from get_client.
    # This is tricky because the problem states "if it's the last retry, this IdealLedTimeout is raised."
    # The current code raises the *last encountered* error. So if get_client fails on retry 1,
    # and then subsequent retries also have get_client failing, the error from the *last* get_client fail will be raised.

    # Let's test the scenario: get_client fails on the *last* retry attempt.
    # All prior retries will have write_gatt_char failing.

    client_effects_for_constructor = [initial_client] # Initial successful connect
    client_write_effects_during_retry = []

    for i in range(max_retries -1): # Retries 1 to MAX_RETRIES-1
        retry_client = create_mock_bleak_client_instance()
        retry_client.write_gatt_char = AsyncMock(side_effect=BleakError(f"Write failed retry {i+1}"))
        client_effects_for_constructor.append(retry_client)
        client_write_effects_during_retry.append(retry_client.write_gatt_char)

    # For the last retry, the BleakClient constructor will raise an error
    client_effects_for_constructor.append(asyncio.TimeoutError("Timeout during get_client on last retry"))

    exit_stack_mock, aclose_mock = create_mock_async_exit_stack(None)
    # enter_async_context will be called for initial_client and each successful retry_client
    successful_clients = [c for c in client_effects_for_constructor if isinstance(c, AsyncMock)]
    exit_stack_mock.enter_async_context.side_effect = successful_clients


    with patch('custom_components.glowswitch.generic_bt_api.device.BleakClient', side_effect=client_effects_for_constructor) as PatchedBleakClient, \
         patch('custom_components.glowswitch.generic_bt_api.device.AsyncExitStack', return_value=exit_stack_mock), \
         patch('custom_components.glowswitch.generic_bt_api.device._LOGGER') as MockLogger, \
         patch('asyncio.sleep', new_callable=AsyncMock) as MockSleep:

        device = GenericBTDevice(mock_ble_device)
        with pytest.raises(IdealLedTimeout, match=reconnect_fail_error_msg):
            await device.write_gatt(TEST_UUID_STR, TEST_DATA_HEX)

        assert PatchedBleakClient.call_count == 1 + max_retries # Initial + all retries attempted instantiation
        assert initial_client.write_gatt_char.call_count == 1
        for write_mock in client_write_effects_during_retry: # write_gatt_char for retries before get_client failed
            assert write_mock.call_count == 1

        assert MockSleep.call_count == max_retries # Sleep before each retry attempt
        assert MockLogger.error.call_args_list[-1].args[0].startswith(f"All {max_retries} retry attempts failed for GATT write")
        assert reconnect_fail_error_msg in str(MockLogger.error.call_args_list[-1].args[2]) # Check last error in log


@pytest.mark.asyncio
async def test_write_gatt_non_service_discovery_bleak_error():
    """6. Non-service-discovery BleakError, no retry logic triggered."""
    mock_ble_device = create_mock_ble_device()
    error_message = "Some other Bleak error, not service discovery"

    ble_client_mock = create_mock_bleak_client_instance()
    ble_client_mock.write_gatt_char = AsyncMock(side_effect=BleakError(error_message))

    exit_stack_mock, _ = create_mock_async_exit_stack(ble_client_mock)

    with patch('custom_components.glowswitch.generic_bt_api.device.BleakClient', return_value=ble_client_mock) as PatchedBleakClient, \
         patch('custom_components.glowswitch.generic_bt_api.device.AsyncExitStack', return_value=exit_stack_mock), \
         patch('custom_components.glowswitch.generic_bt_api.device._LOGGER') as MockLogger, \
         patch('asyncio.sleep', new_callable=AsyncMock) as MockSleep:

        device = GenericBTDevice(mock_ble_device)
        with pytest.raises(BleakError, match=error_message):
            await device.write_gatt(TEST_UUID_STR, TEST_DATA_HEX)

        PatchedBleakClient.assert_called_once()
        ble_client_mock.write_gatt_char.assert_called_once()
        MockSleep.assert_not_called()

        # Ensure no service discovery retry logs were made
        assert not any("Service discovery error for" in call_item.args[0] for call_item in MockLogger.warning.call_args_list)
        assert not any("Retry attempt" in call_item.args[0] for call_item in MockLogger.info.call_args_list)

# Remove old tests that are now superseded or less specific
# The tests test_write_gatt_retry_succeeds, test_write_gatt_retry_fails,
# test_write_gatt_other_bleak_error, test_write_gatt_retry_succeeds_with_logging,
# and test_write_gatt_reconnect_fails from the previous file version are covered by the new, more detailed tests.
# This overwrite will replace them.
