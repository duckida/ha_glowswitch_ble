"""Config flow for GlowSwitch integration."""
from __future__ import annotations

import logging
from typing import Any

from bluetooth_data_tools import human_readable_name
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN
from .generic_bt_api.device import (
    GlowSwitchDevice,
    GlowSwitchTimeout,
    GlowSwitchBleakError,
)

_LOGGER = logging.getLogger(__name__)

GLOWDIM_SERVICE_UUID = "12345678-1234-5678-1234-56789abcdefa"
GLOWSWITCH_SERVICE_UUID = "12345678-1234-5678-1234-56789abcdef0"


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for GlowSwitch."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle the bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        # Test connection before showing confirmation
        device = GlowSwitchDevice(discovery_info.device)
        # Retry connection test a few times
        for i in range(3):  # Retry 3 times
            try:
                # A simple command to test connection, like turning it off (0x00)
                await device.send_command(bytearray([0x00]))
                break  # If successful, break the loop
            except (GlowSwitchTimeout, GlowSwitchBleakError) as e:
                _LOGGER.warning(
                    "Connection test failed for %s (attempt %d/%d): %s",
                    discovery_info.address,
                    i + 1,
                    3,
                    e,
                )
                if i == 2:  # If last attempt failed
                    return self.async_abort(reason="cannot_connect")
                await asyncio.sleep(5)  # Wait 5 seconds before retrying
            except Exception:
                _LOGGER.exception("Unexpected error during device validation")
                return self.async_abort(reason="unknown")

        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {
            "name": human_readable_name(
                None, discovery_info.name, discovery_info.address
            )
        }
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        if user_input is not None:
            device_type = self._get_device_type(self._discovery_info)
            return self.async_create_entry(
                title=self.context["title_placeholders"]["name"],
                data={
                    CONF_ADDRESS: self._discovery_info.address,
                    "device_type": device_type,
                },
            )

        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders=self.context["title_placeholders"],
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step to pick a discovered device (manual setup)."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured(updates_allowed=True)
            
            discovery_info = self._discovered_devices[address]
            device_type = self._get_device_type(discovery_info)

            return self.async_create_entry(
                title=discovery_info.name,
                data={
                    CONF_ADDRESS: discovery_info.address,
                    "device_type": device_type,
                },
            )

        # Discover devices for manual selection
        current_addresses = self._async_current_ids()
        for discovery in async_discovered_service_info(self.hass):
            if discovery.address in current_addresses or discovery.address in self._discovered_devices:
                continue
            self._discovered_devices[discovery.address] = discovery

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        data_schema = vol.Schema(
            {
                vol.Required(CONF_ADDRESS): vol.In(
                    {
                        address: f"{info.name} ({address})"
                        for address, info in self._discovered_devices.items()
                    }
                )
            }
        )
        return self.async_show_form(step_id="user", data_schema=data_schema)

    def _get_device_type(self, discovery_info: BluetoothServiceInfoBleak) -> str:
        """Determine device type from service UUIDs."""
        service_uuids = [
            str(s).lower() for s in discovery_info.advertisement.service_uuids
        ]
        if GLOWDIM_SERVICE_UUID in service_uuids:
            return "glowdim"
        return "glowswitch"
