"""An abstract class common to all Generic BT entities."""
from __future__ import annotations

import logging

from homeassistant.components.bluetooth.passive_update_coordinator import PassiveBluetoothCoordinatorEntity
from homeassistant.helpers import device_registry as dr

from .coordinator import GenericBTCoordinator # Changed import

_LOGGER = logging.getLogger(__name__)

class GenericBTEntity(PassiveBluetoothCoordinatorEntity[GenericBTCoordinator]): # Renamed class and type hint
    """Generic entity encapsulating common features of GlowSwitch device.""" # Docstring can remain

    _device: GenericBTDevice # Changed type hint
    _attr_has_entity_name = True

    def __init__(self, coordinator: GenericBTCoordinator) -> None: # Changed type hint
        """Initialize the entity."""
        super().__init__(coordinator)
        self._device = coordinator.device
        self._address = coordinator.ble_device.address
        self._attr_unique_id = coordinator.base_unique_id
        self._attr_device_info = {
            "connections":{(dr.CONNECTION_BLUETOOTH, self._address)},
            "name":coordinator.device_name
        }
