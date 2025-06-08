"""Tests for the GlowSwitch config flow."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bleak.exc import BleakError

from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_ADDRESS
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

# Import the actual UUIDs from config_flow to ensure tests use the same values
from custom_components.glowswitch.config_flow import ConfigFlow, GLOWDIM_SERVICE_UUID, GLOWSWITCH_SERVICE_UUID
from custom_components.glowswitch.const import DOMAIN

# Define a common test address
TEST_ADDRESS = "test-address-12:34:56"
TEST_NAME = "TestDevice"

# Mock data for BluetoothServiceInfoBleak
def generate_ble_service_info(
    name: str = TEST_NAME,
    address: str = TEST_ADDRESS,
    service_uuids: list[str] | None = None,
    rssi: int = -60,
    manufacturer_data=None,
    service_data=None,
) -> BluetoothServiceInfoBleak:
    """Generate a BluetoothServiceInfoBleak object for testing."""
    if manufacturer_data is None:
        manufacturer_data = {}
    if service_data is None:
        service_data = {}

    # Ensure service_uuids are correctly formatted if provided
    # The BluetoothServiceInfoBleak expects them as strings already.
    _service_uuids = service_uuids if service_uuids is not None else []

    return BluetoothServiceInfoBleak(
        name=name,
        address=address,
        rssi=rssi,
        manufacturer_data=manufacturer_data,
        service_data=service_data,
        service_uuids=_service_uuids,
        source="local",
        device=MagicMock(), # bleak.backends.device.BLEDevice
        advertisement=MagicMock(), # bleak.backends.scanner.AdvertisementData
        time=0,
        connectable=True,
        tx_power=-127 # Using a default value as it's required.
    )

@pytest.fixture(autouse=True)
def mock_dependencies():
    """Mock dependencies for the config flow tests."""
    with patch("custom_components.glowswitch.config_flow.GenericBTDevice") as mock_device_class:
        mock_device_instance = mock_device_class.return_value
        mock_device_instance.update = AsyncMock()
        mock_device_instance.stop = AsyncMock()
        yield

@pytest.fixture
async def mock_ha_config_flow_manager(hass: HomeAssistant):
    """Fixture to mock Home Assistant's config flow manager."""
    await config_entries.HANDLERS.async_get(DOMAIN) # Ensure handler is loaded

# Common setup for initiating a flow test
async def inicia_config_flow(hass: HomeAssistant, service_info: BluetoothServiceInfoBleak):
    """Initiate a config flow with the given service info."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_BLUETOOTH}, data=service_info
    )
    return result

async def test_discovery_glowdim_by_uuid(hass: HomeAssistant, mock_ha_config_flow_manager):
    """Test discovery for a Glowdim device identified by its Service UUID."""
    service_info = generate_ble_service_info(
        name="Glowdim Device", # Name is arbitrary
        service_uuids=[GLOWDIM_SERVICE_UUID]
    )
    result = await inicia_config_flow(hass, service_info)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_ADDRESS: TEST_ADDRESS}
    )
    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Glowdim Device"
    assert result2["data"][CONF_ADDRESS] == TEST_ADDRESS
    assert result2["data"]["device_type"] == "glowdim"

async def test_discovery_glowswitch_by_uuid(hass: HomeAssistant, mock_ha_config_flow_manager):
    """Test discovery for a Glowswitch device identified by its Service UUID."""
    service_info = generate_ble_service_info(
        name="Glowswitch Device", # Name is arbitrary
        service_uuids=[GLOWSWITCH_SERVICE_UUID]
    )
    result = await inicia_config_flow(hass, service_info)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_ADDRESS: TEST_ADDRESS}
    )
    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Glowswitch Device"
    assert result2["data"][CONF_ADDRESS] == TEST_ADDRESS
    assert result2["data"]["device_type"] == "glowswitch"

async def test_discovery_glowdim_priority_both_uuids(hass: HomeAssistant, mock_ha_config_flow_manager):
    """Test Glowdim identification if both known Service UUIDs are advertised."""
    service_info = generate_ble_service_info(
        name="Dual UUID Device",
        service_uuids=[GLOWDIM_SERVICE_UUID, GLOWSWITCH_SERVICE_UUID]
    )
    result = await inicia_config_flow(hass, service_info)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_ADDRESS: TEST_ADDRESS}
    )
    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Dual UUID Device"
    assert result2["data"]["device_type"] == "glowdim" # Glowdim UUID should take priority

async def test_discovery_default_glowswitch_no_known_uuids(hass: HomeAssistant, mock_ha_config_flow_manager):
    """Test device defaults to glowswitch if no known Service UUIDs are advertised."""
    service_info = generate_ble_service_info(
        name="Unknown Device",
        service_uuids=["some-random-uuid-1234", "another-unknown-uuid-5678"] # No known UUIDs
    )
    result = await inicia_config_flow(hass, service_info)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_ADDRESS: TEST_ADDRESS}
    )
    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Unknown Device"
    assert result2["data"]["device_type"] == "glowswitch" # Should default to glowswitch

async def test_discovery_default_glowswitch_empty_uuids(hass: HomeAssistant, mock_ha_config_flow_manager):
    """Test device defaults to glowswitch if service UUIDs list is empty."""
    service_info = generate_ble_service_info(
        name="Empty UUIDs Device",
        service_uuids=[]
    )
    result = await inicia_config_flow(hass, service_info)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_ADDRESS: TEST_ADDRESS}
    )
    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Empty UUIDs Device"
    assert result2["data"]["device_type"] == "glowswitch" # Should default to glowswitch

@patch("homeassistant.components.bluetooth.async_discovered_service_info")
async def test_user_step_no_devices_found(mock_async_discovered_service_info, hass: HomeAssistant, mock_ha_config_flow_manager):
    """Test user step when no devices are discovered."""
    mock_async_discovered_service_info.return_value = [] # No devices found

    # Initiate flow without bluetooth discovery (e.g., user initiated)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "no_devices_found"

async def test_user_step_connect_error(hass: HomeAssistant, mock_ha_config_flow_manager):
    """Test user step when device connection fails."""
    service_info = generate_ble_service_info(name="ConnectFailDevice")

    # Mock GenericBTDevice.update to raise an error
    with patch("custom_components.glowswitch.config_flow.GenericBTDevice") as mock_device_class:
        mock_device_instance = mock_device_class.return_value
        mock_device_instance.update = AsyncMock(side_effect=BleakError("Connection failed"))
        mock_device_instance.stop = AsyncMock()

        result = await inicia_config_flow(hass, service_info) # Starts with bluetooth discovery
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_ADDRESS: TEST_ADDRESS}
        )
        assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM # Should show form again
        assert result2["errors"]["base"] == "cannot_connect"

async def test_user_step_already_configured(hass: HomeAssistant, mock_ha_config_flow_manager):
    """Test flow when device is already configured."""
    service_info = generate_ble_service_info(name="AlreadyConfigured")

    # Pre-configure an entry with the same unique ID (address)
    mock_entry = MagicMock(spec=config_entries.ConfigEntry)
    mock_entry.source = config_entries.SOURCE_BLUETOOTH
    mock_entry.unique_id = TEST_ADDRESS # This is what async_set_unique_id uses

    # To mock this correctly, we need to ensure that when async_set_unique_id is called,
    # it finds an existing entry. This is typically managed by hass.config_entries.async_entries()
    # For this test, we can directly use _abort_if_unique_id_configured by setting unique_id on flow handler

    with patch.object(ConfigFlow, "async_set_unique_id") as mock_set_unique_id:
        # This mock will allow the flow to proceed past the first unique_id check in async_step_bluetooth
        # but we want to test the check in async_step_user or the general abort.
        # A better way is to let async_set_unique_id do its job and have a configured entry.

        # Let's try by creating a dummy entry first.
        # This requires a bit more setup for the mock ConfigEntry.
        entry = config_entries.ConfigEntry(
            version=1,
            domain=DOMAIN,
            entry_id="existing_entry_id",
            data={CONF_ADDRESS: TEST_ADDRESS, "device_type": "glowswitch"},
            title="Existing Device",
            source=config_entries.SOURCE_BLUETOOTH,
            unique_id=TEST_ADDRESS, # This is the key for duplication check
        )
        hass.config_entries._entries[entry.entry_id] = entry # Add to hass internal store for test

        result = await inicia_config_flow(hass, service_info)

        # The first check in async_step_bluetooth should catch this.
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "already_configured"

        # Cleanup the dummy entry if necessary, though pytest isolation should handle it.
        del hass.config_entries._entries[entry.entry_id]

# Review test_light.py:
# The tests in test_light.py (e.g., test_light_properties_glowdim, test_light_turn_on_glowdim_with_brightness)
# directly set mock_config_entry.data = {**MOCK_CONFIG_ENTRY_DATA, "device_type": "glowdim"}.
# This is consistent with the expected output of the config flow. For example, if the config flow
# correctly identifies a device as "glowdim" (e.g., via Service UUID), it will store "glowdim"
# in the entry.data. The light entity tests then pick this up.
# No changes seem necessary for test_light.py based on this review.

"""
