from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.light import LightEntityFeature, ATTR_BRIGHTNESS # Added ATTR_BRIGHTNESS

from custom_components.glowswitch.light import GenericBTLight, async_setup_entry
from custom_components.glowswitch.coordinator import GenericBTCoordinator
from custom_components.glowswitch.const import DOMAIN

# Mock ConfigEntry data
MOCK_CONFIG_ENTRY_DATA = {
    "address": "test_address",
    "name": "Test GlowSwitch"
}

# Mock unique_id for ConfigEntry
MOCK_CONFIG_ENTRY_UNIQUE_ID = "test_unique_id"

@pytest.fixture
def mock_coordinator():
    coordinator = MagicMock(spec=GenericBTCoordinator) # Updated spec
    coordinator.device = AsyncMock() # Mocks the GenericBTDevice
    coordinator.device.write_gatt = AsyncMock()
    coordinator.device_info = {
        "connections": {("bluetooth", "test_address")},
        "name": "Test GlowSwitch Device"
    }
    coordinator.base_unique_id = "coordinator_unique_id"
    coordinator.device_name = "Test GlowSwitch Device"
    return coordinator

@pytest.fixture
def mock_config_entry():
    config_entry = MagicMock(spec=ConfigEntry)
    # Update MOCK_CONFIG_ENTRY_DATA to include a default device_type or modify in tests
    config_entry.data = {**MOCK_CONFIG_ENTRY_DATA, "device_type": "glowswitch"} # Default to glowswitch for existing tests
    config_entry.unique_id = MOCK_CONFIG_ENTRY_UNIQUE_ID
    config_entry.entry_id = "test_entry_id"
    return config_entry

async def test_async_setup_entry(hass: HomeAssistant, mock_coordinator, mock_config_entry):
    """Test the async_setup_entry function."""
    hass.data = {DOMAIN: {mock_config_entry.entry_id: mock_coordinator}}
    async_add_entities_mock = AsyncMock()

    await async_setup_entry(hass, mock_config_entry, async_add_entities_mock)

    async_add_entities_mock.assert_called_once()
    # Get the GenericBTLight instance from the call arguments
    light_instance = async_add_entities_mock.call_args[0][0][0]
    assert isinstance(light_instance, GenericBTLight) # Updated isinstance check
    assert light_instance.unique_id == f"{MOCK_CONFIG_ENTRY_UNIQUE_ID}_light"
    assert light_instance.name == "GlowSwitch Light" # As defined in light.py - This remains


async def test_light_turn_on_glowswitch(mock_coordinator, mock_config_entry):
    """Test the turn_on method for a glowswitch device."""
    mock_config_entry.data = {**MOCK_CONFIG_ENTRY_DATA, "device_type": "glowswitch"}
    light = GenericBTLight(mock_coordinator, mock_config_entry)
    light.async_write_ha_state = AsyncMock()

    assert light.is_on is None
    await light.async_turn_on()

    mock_coordinator.device.write_gatt.assert_called_once_with(
        "12345678-1234-5678-1234-56789abcdef1", bytes("01", "utf-8")
    )
    assert light.is_on is True
    light.async_write_ha_state.assert_called_once()

async def test_light_turn_off_glowswitch(mock_coordinator, mock_config_entry):
    """Test the turn_off method for a glowswitch device."""
    mock_config_entry.data = {**MOCK_CONFIG_ENTRY_DATA, "device_type": "glowswitch"}
    light = GenericBTLight(mock_coordinator, mock_config_entry)
    light.async_write_ha_state = AsyncMock()

    light._is_on = True 
    assert light.is_on is True
    await light.async_turn_off()

    mock_coordinator.device.write_gatt.assert_called_once_with(
        "12345678-1234-5678-1234-56789abcdef1", bytes("00", "utf-8")
    )
    assert light.is_on is False
    light.async_write_ha_state.assert_called_once()

def test_light_is_on_initial_glowswitch(mock_coordinator, mock_config_entry):
    """Test the is_on property initial state for a glowswitch."""
    mock_config_entry.data = {**MOCK_CONFIG_ENTRY_DATA, "device_type": "glowswitch"}
    light = GenericBTLight(mock_coordinator, mock_config_entry)
    assert light.is_on is None

def test_light_properties_glowswitch(mock_coordinator, mock_config_entry):
    """Test basic properties of a glowswitch device."""
    mock_config_entry.data = {**MOCK_CONFIG_ENTRY_DATA, "device_type": "glowswitch"}
    light = GenericBTLight(mock_coordinator, mock_config_entry)
    assert light.unique_id == f"{MOCK_CONFIG_ENTRY_UNIQUE_ID}_light"
    assert light.name == "GlowSwitch Light"
    assert light.supported_features == LightEntityFeature(0) # Explicitly 0 for no features
    assert light.brightness is None

# --- Tests for "glowdim" device type ---

def test_light_properties_glowdim(mock_coordinator, mock_config_entry):
    """Test basic properties of a glowdim device."""
    mock_config_entry.data = {**MOCK_CONFIG_ENTRY_DATA, "device_type": "glowdim"}
    light = GenericBTLight(mock_coordinator, mock_config_entry)

    assert light.unique_id == f"{MOCK_CONFIG_ENTRY_UNIQUE_ID}_light"
    assert light.name == "GlowSwitch Light"
    assert light.supported_features == LightEntityFeature.BRIGHTNESS
    assert light.brightness == 255 # Initial HA brightness
    assert light.is_on is None

async def test_light_turn_on_glowdim_with_brightness(mock_coordinator, mock_config_entry):
    """Test turning on a glowdim device with specified brightness."""
    mock_config_entry.data = {**MOCK_CONFIG_ENTRY_DATA, "device_type": "glowdim"}
    light = GenericBTLight(mock_coordinator, mock_config_entry)
    light.async_write_ha_state = AsyncMock()

    await light.async_turn_on(**{ATTR_BRIGHTNESS: 128})

    # HA 128 -> Device (128/255 * 100) = 50.196... -> rounded to 50
    mock_coordinator.device.write_gatt.assert_called_once_with(
        "12345678-1234-5678-1234-56789abcdef1", bytes([50])
    )
    assert light.is_on is True
    assert light.brightness == 128
    light.async_write_ha_state.assert_called_once()

async def test_light_turn_on_glowdim_without_brightness_initial(mock_coordinator, mock_config_entry):
    """Test turning on a glowdim device without specified brightness (initial call)."""
    mock_config_entry.data = {**MOCK_CONFIG_ENTRY_DATA, "device_type": "glowdim"}
    light = GenericBTLight(mock_coordinator, mock_config_entry)
    light.async_write_ha_state = AsyncMock()

    # Initial brightness is 255, so device value should be 100
    await light.async_turn_on()

    mock_coordinator.device.write_gatt.assert_called_once_with(
        "12345678-1234-5678-1234-56789abcdef1", bytes([100])
    )
    assert light.is_on is True
    assert light.brightness == 255 # Stays at initial full brightness
    light.async_write_ha_state.assert_called_once()

async def test_light_turn_on_glowdim_without_brightness_after_set(mock_coordinator, mock_config_entry):
    """Test turning on a glowdim device without brightness after it was previously set."""
    mock_config_entry.data = {**MOCK_CONFIG_ENTRY_DATA, "device_type": "glowdim"}
    light = GenericBTLight(mock_coordinator, mock_config_entry)
    light.async_write_ha_state = AsyncMock()

    # Set an initial brightness
    await light.async_turn_on(**{ATTR_BRIGHTNESS: 77}) # HA 77 -> Device (77/255 * 100) = 30.19 -> 30
    assert light.is_on is True
    assert light.brightness == 77
    mock_coordinator.device.write_gatt.assert_called_with(
        "12345678-1234-5678-1234-56789abcdef1", bytes([30])
    )
    light.async_write_ha_state.assert_called_once()

    # Reset mocks and turn off (state change, but doesn't clear brightness)
    mock_coordinator.device.write_gatt.reset_mock()
    light.async_write_ha_state.reset_mock()
    light._is_on = False # Simulate being off, brightness remains 77

    # Turn on again without specifying brightness
    await light.async_turn_on()

    # Should use the previously set brightness (77 HA -> 30 device)
    mock_coordinator.device.write_gatt.assert_called_once_with(
        "12345678-1234-5678-1234-56789abcdef1", bytes([30])
    )
    assert light.is_on is True
    assert light.brightness == 77 # Brightness remains as previously set
    light.async_write_ha_state.assert_called_once()


async def test_light_turn_off_glowdim(mock_coordinator, mock_config_entry):
    """Test turning off a glowdim device."""
    mock_config_entry.data = {**MOCK_CONFIG_ENTRY_DATA, "device_type": "glowdim"}
    light = GenericBTLight(mock_coordinator, mock_config_entry)
    light.async_write_ha_state = AsyncMock()

    # Set initial state to on for testing turn_off
    light._is_on = True
    light._brightness = 150 # Some brightness value
    assert light.is_on is True

    await light.async_turn_off()

    mock_coordinator.device.write_gatt.assert_called_once_with(
        "12345678-1234-5678-1234-56789abcdef1", bytes([0x00])
    )
    assert light.is_on is False
    # Brightness should remain as it was, for next turn_on
    assert light.brightness == 150
    light.async_write_ha_state.assert_called_once()
