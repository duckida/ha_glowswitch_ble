### Project Overview

This project is a Home Assistant integration for "GlowSwitch" Bluetooth LE devices. It allows users to control these devices (likely lights) through Home Assistant. The integration supports two types of devices: "glowswitch" (a simple on/off switch) and "glowdim" (a dimmable light).

### File Breakdown

-   `README.md`: Provides a brief introduction to the integration and its features.
-   `hacs.json`: HACS (Home Assistant Community Store) manifest file.
-   `custom_components/glowswitch/`: The main integration directory.
    -   `__init__.py`: The entry point of the integration. It sets up the connection to the GlowSwitch device and initializes the coordinator.
    -   `binary_sensor.py`: Creates a binary sensor entity that represents the connection status of the device. It also exposes services to read and write raw GATT characteristics.
    -   `config_flow.py`: Handles the configuration process for the integration. It discovers GlowSwitch devices using Bluetooth service UUIDs and allows the user to add them to Home Assistant. It differentiates between "glowswitch" and "glowdim" devices based on the advertised service UUIDs.
    -   `const.py`: Defines constants used throughout the integration, such as the domain name and service schemas.
    -   `coordinator.py`: Implements the `DataUpdateCoordinator` which manages the state of the device and communication with it.
    -   `entity.py`: A base entity class that provides common functionality for all GlowSwitch entities.
    -   `light.py`: Defines the `light` entity for controlling the GlowSwitch device. It supports on/off for "glowswitch" devices and brightness control for "glowdim" devices.
    -   `manifest.json`: The integration manifest file, containing metadata like the domain, name, version, and dependencies.
    -   `services.yaml`: Defines the custom services (`write_gatt` and `read_gatt`) that can be called from Home Assistant.
    -   `generic_bt_api/`: A sub-package for the generic Bluetooth device API.
        -   `const.py`: Constants for the API.
        -   `device.py`: A generic Bluetooth device class that handles the low-level communication with the device (reading and writing GATT characteristics).
    -   `tests/`: Contains unit tests for the integration.
        -   `test_config_flow.py`: Tests for the configuration flow.
        -   `test_light.py`: Tests for the light entity.
