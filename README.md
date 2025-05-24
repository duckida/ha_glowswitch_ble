# glowswitch
GlowSwitch Integration for Home Assistant

Please check the community discussion for more information: [GlowSwitch Integration discussion](https://community.home-assistant.io/t/generic-bluetooth-integration/648952)

## Entities

### Light

A `light` entity is created for each GlowSwitch device. This entity allows you to turn the device on and off.

*   **On/Off Control:** The light is controlled by writing to the Bluetooth characteristic `12345678-1234-5678-1234-56789abcdef1`. Sending `01` turns the device on, and `00` turns it off.
*   **Home Assistant:** It will appear as a standard on/off switchable light in your Home Assistant dashboard.
