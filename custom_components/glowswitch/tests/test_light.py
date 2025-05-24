from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.light import LightEntityFeature

from custom_components.glowswitch.light import GlowSwitchLight, async_setup_entry
from custom_components.glowswitch.coordinator import GlowSwitchCoordinator
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
    coordinator = MagicMock(spec=GlowSwitchCoordinator)
    coordinator.device = AsyncMock() # Mocks the GlowSwitchDevice
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
    config_entry.data = MOCK_CONFIG_ENTRY_DATA
    config_entry.unique_id = MOCK_CONFIG_ENTRY_UNIQUE_ID
    config_entry.entry_id = "test_entry_id"
    return config_entry

async def test_async_setup_entry(hass: HomeAssistant, mock_coordinator, mock_config_entry):
    """Test the async_setup_entry function."""
    hass.data = {DOMAIN: {mock_config_entry.entry_id: mock_coordinator}}
    async_add_entities_mock = AsyncMock()

    await async_setup_entry(hass, mock_config_entry, async_add_entities_mock)

    async_add_entities_mock.assert_called_once()
    # Get the GlowSwitchLight instance from the call arguments
    light_instance = async_add_entities_mock.call_args[0][0][0]
    assert isinstance(light_instance, GlowSwitchLight)
    assert light_instance.unique_id == f"{MOCK_CONFIG_ENTRY_UNIQUE_ID}_light"
    assert light_instance.name == "GlowSwitch Light" # As defined in light.py


async def test_light_turn_on(mock_coordinator, mock_config_entry):
    """Test the turn_on method of the GlowSwitchLight entity."""
    light = GlowSwitchLight(mock_coordinator, mock_config_entry)
    light.async_write_ha_state = AsyncMock() # Mock this method

    assert light.is_on is None # Initial state

    await light.async_turn_on()

    mock_coordinator.device.write_gatt.assert_called_once_with(
        "12345678-1234-5678-1234-56789abcdef1", "01"
    )
    assert light.is_on is True
    light.async_write_ha_state.assert_called_once()

async def test_light_turn_off(mock_coordinator, mock_config_entry):
    """Test the turn_off method of the GlowSwitchLight entity."""
    light = GlowSwitchLight(mock_coordinator, mock_config_entry)
    light.async_write_ha_state = AsyncMock() # Mock this method

    # Set initial state to on for testing turn_off
    light._is_on = True 
    assert light.is_on is True

    await light.async_turn_off()

    mock_coordinator.device.write_gatt.assert_called_once_with(
        "12345678-1234-5678-1234-56789abcdef1", "00"
    )
    assert light.is_on is False
    light.async_write_ha_state.assert_called_once()

def test_light_is_on_initial(mock_coordinator, mock_config_entry):
    """Test the is_on property initial state."""
    light = GlowSwitchLight(mock_coordinator, mock_config_entry)
    assert light.is_on is None # Or False, depending on implementation

def test_light_properties(mock_coordinator, mock_config_entry):
    """Test basic properties of the GlowSwitchLight entity."""
    light = GlowSwitchLight(mock_coordinator, mock_config_entry)
    assert light.unique_id == f"{MOCK_CONFIG_ENTRY_UNIQUE_ID}_light"
    assert light.name == "GlowSwitch Light"
    # As we removed _attr_supported_features, it should default.
    # For a basic on/off light, this might be 0 or None.
    # If specific features are expected by default, test for them.
    # For now, let's assume no specific features beyond on/off.
    assert light.supported_features == 0 # Or test for None if that's the default
