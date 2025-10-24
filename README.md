# XTool Home Assistant Integration

This is a custom integration for Home Assistant to interface with the XTool laser engraver.

## Features
- Displays the current status of the XTool (e.g., "Running", "Idle", "Sleep").
- Can be integrated into Home Assistant for monitoring and automation.
- Supports multiple machines

## Installation

### HACS

1. Add as this repo as a custom repo in HACS
1. Search for Xtool in HACS and install

## Manual Install

1. Download or clone this repository.
2. Place the `xtool` folder in the `custom_components` directory of your Home Assistant installation.

## Configuration

Add the following to your `configuration.yaml`:

```yaml
sensor:
  - platform: xtool
    name: p2_laser
    device_type: p2
    ip_address: "xxx.xxx.xxx.xxx"  # Replace with the IP address of your XTool
  - platform: xtool
    device_type: f1
    name: f1_laser
    ip_address: "xxx.xxx.xxx.xxx"  # Replace with the IP address of your XTool
  - platform: xtool
    device_type: m1
    name: m1_laser
    ip_address: "xxx.xxx.xxx.xxx"
```

## Usage

Once the integration is installed and configured, a sensor will be created in Home Assistant displaying the current status of the XTool. The status values can include:

- **Running**: The XTool is currently running.
- **Done**: The work is completed.
- **Idle**: The XTool is idle.
- **Sleep**: The XTool is in sleep mode.
- **Unknown**: The status could not be retrieved.

You can use these sensor states in automations to monitor and control the XTool's activities.

## Example Automation

``` yaml
alias: P2 Exhaust Fan
description: "Turns the exhaust fan on and off"
triggers:
  - trigger: state
    entity_id:
      - sensor.p2_laser_status
    from: null
conditions: []
actions:
  - if:
      - condition: state
        entity_id: sensor.p2_laser_status
        state: Running
    then:
      - type: turn_on
        device_id: a3f5b6c7d8e9f0a1b2c3d4e5f6a7b8c9
        entity_id: d4e5f6a7b8c9a3f5b6c7d8e9f0a1b2c3
        domain: switch
    else:
      - type: turn_off
        device_id: a3f5b6c7d8e9f0a1b2c3d4e5f6a7b8c9
        entity_id: f0a1b2c3d4e5f6a7b8c9a3f5b6c7d8e9
        domain: switch
mode: single
```
## Support My Work
If you enjoy my projects or find them useful, consider supporting me on [Ko-fi](https://ko-fi.com/bassxt)!

[![Support me on Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/bassxt)

