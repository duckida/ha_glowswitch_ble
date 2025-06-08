"""Config flow for GenericBT integration."""
from __future__ import annotations

import logging
from typing import Any

from bluetooth_data_tools import human_readable_name
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak, async_discovered_service_info
from homeassistant.const import CONF_ADDRESS
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN
from .generic_bt_api.device import GenericBTDevice # Changed import path and class name

_LOGGER = logging.getLogger(__name__)

# GLOWDIM_SERVICE_UUID constant removed

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for GlowSwitch."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(self, discovery_info: BluetoothServiceInfoBleak) -> FlowResult:
        """Handle the bluetooth discovery step."""
        #if discovery_info.name.startswith(UNSUPPORTED_SUB_MODEL):
        #    return self.async_abort(reason="not_supported")

        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {"name": human_readable_name(None, discovery_info.name, discovery_info.address)}
        # self._device_type is not strictly needed here if async_step_user handles it
        # based on the chosen or current discovery_info.
        return await self.async_step_user()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the user step to pick discovered device."""
        errors: dict[str, str] = {}
        processed_discovery_info: BluetoothServiceInfoBleak | None = None

        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            processed_discovery_info = self._discovered_devices[address] # Use this for the selected device
        elif self._discovery_info:
            # Came directly from bluetooth discovery
            processed_discovery_info = self._discovery_info
            # Ensure it's in _discovered_devices for consistency if we show form again
            self._discovered_devices[processed_discovery_info.address] = processed_discovery_info

        if processed_discovery_info:
            local_name = processed_discovery_info.name
            # Determine device_type for the specific device being processed based on its name
            if "glowdim" in local_name.lower():
                device_type = "glowdim"
            else:
                device_type = "glowswitch"

            # If user_input is present, we are trying to create the entry
            if user_input is not None:
                await self.async_set_unique_id(processed_discovery_info.address, raise_on_progress=False)
                self._abort_if_unique_id_configured()
                device = GenericBTDevice(processed_discovery_info.device) # Changed class instantiation
                try:
                    await device.update()
                except BLEAK_EXCEPTIONS:
                    errors["base"] = "cannot_connect"
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception("Unexpected error")
                    errors["base"] = "unknown"
                else:
                    await device.stop()
                    return self.async_create_entry(
                        title=local_name,
                        data={
                            CONF_ADDRESS: processed_discovery_info.address,
                            "device_type": device_type, # Add device_type here
                        }
                    )
        # Fallback to populate _discovered_devices if empty or if no specific device processed yet
        if not self._discovered_devices and not processed_discovery_info:
            current_addresses = self._async_current_ids()
            for discovery_in_list in async_discovered_service_info(self.hass): # renamed discovery to discovery_in_list
                if (
                    discovery_in_list.address in current_addresses
                    or discovery_in_list.address in self._discovered_devices
                ):
                    continue
                self._discovered_devices[discovery_in_list.address] = discovery_in_list

        if discovery := self._discovery_info: # Keep this to add initial discovery to the list if not already processed
            if discovery.address not in self._discovered_devices:
                 self._discovered_devices[discovery.address] = discovery
        # else: # This else block might be problematic if processed_discovery_info was set from self._discovery_info
        # The logic for populating _discovered_devices for the form needs to be robust
        # Ensure _discovered_devices is populated for the form if we haven't created an entry or aborted
        if not user_input and not errors: # only populate from scratch if not handling a submission
            # This part populates the list for the user to choose from
            current_addresses = self._async_current_ids()
            # Check if self._discovery_info (if any) is already added
            if self._discovery_info and self._discovery_info.address not in self._discovered_devices:
                self._discovered_devices[self._discovery_info.address] = self._discovery_info

            for discovery_in_list in async_discovered_service_info(self.hass):
                if (
                    discovery_in_list.address in current_addresses
                    or discovery_in_list.address in self._discovered_devices
                ):
                    continue
                self._discovered_devices[discovery_in_list.address] = discovery_in_list

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")
        # If we are showing the form (either first time, or after an error)
        # Ensure data_schema is prepared with available devices
        data_schema = vol.Schema(
            {
                vol.Required(CONF_ADDRESS): vol.In(
                    {
                        service_info.address: (f"{service_info.name} ({service_info.address})")
                        for service_info in self._discovered_devices.values() # Ensure this is populated
                    }
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)