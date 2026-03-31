# XTool Home Assistant Integration

This is a **custom integration for Home Assistant** that connects and monitors **xTool laser engravers** such as **P2**, **F1**, **M1**, and **Apparel**.

> ⚠️ This integration is an independent community project.  
> I am **not affiliated with xTool** or its employees — but I’d love to collaborate with the xTool team for further testing 😉.

---

## ✨ Features

- **Native Home Assistant integration** (no YAML required)
- **Multiple devices supported** — each xTool appears as its own device
- **Automatic entity creation** per device:
  - `binary_sensor.<name>_<device_type>_power` → shows if the machine is reachable/on
  - `sensor.<name>_<device_type>_status` → shows the current working state
  - **M1** adds extra sensors:
    - `sensor.<name>_m1_cpu_temp`
    - `sensor.<name>_m1_water_temp`
    - `sensor.<name>_m1_purifier`
- Typical status values: `Running`, `Done`, `Idle`, `Sleep`, `Ready`, `Unavailable`, `Unknown`

---

## 🧩 Installation

### via HACS (recommended)
1. Add this repository as a **Custom Repository** in HACS.  
2. Search for **“XTool”** and install.  
3. Restart Home Assistant.

### Manual Installation
1. Download or clone this repository.  
2. Copy the folder `xtool` into your `config/custom_components/` directory.  
3. Restart Home Assistant.

---

## ⚙️ Configuration (UI)

1. Go to **Settings → Devices & Services → Add Integration**.  
2. Search for **“XTool”**.  
3. Enter:
   - **Name** → freely chosen (e.g. `Laser1`)
   - **IP Address** → IP of your xTool device
   - **Device Type** → choose between `P2`, `F1`, `M1`, or `Apparel`
4. Confirm — done ✅  

Each device automatically creates the appropriate entities in Home Assistant based on its **`name`** and **`device_type`**.

---

## 🆔 Entity Naming

Entity IDs are automatically generated using the **Name** and **Device Type** you provide during setup:

| Example | Entities Created |
|----------|------------------|
| Name: `Laser1`, Type: `F1` | `binary_sensor.laser1_f1_power`<br>`sensor.laser1_f1_status` |
| Name: `Laser2`, Type: `P2` | `binary_sensor.laser2_p2_power`<br>`sensor.laser2_p2_status` |
| Name: `Studio`, Type: `M1` | `sensor.studio_m1_status`<br>`sensor.studio_m1_cpu_temp`<br>`sensor.studio_m1_water_temp`<br>`sensor.studio_m1_purifier` |
| Name: `Laser3`, Type: `S1` | `binary_sensor.laser3_s1_power`<br>`binary_sensor.laser3_s1_running`<br>`binary_sensor.laser3_s1_alarm`<br>`sensor.laser3_s1_status`<br>`sensor.laser3_s1_firmware_version`<br>`sensor.laser3_s1_job_file`<br>`sensor.laser3_s1_position_x`<br>`sensor.laser3_s1_position_y`<br>`sensor.laser3_s1_fan_a`<br>`sensor.laser3_s1_fan_b` |

**S1 with AP2 Air Cleaner** adds these additional entities (using the same name prefix):

| Entity | Description |
|--------|-------------|
| `binary_sensor.laser3_s1_air_cleaner` | Air cleaner running state |
| `sensor.laser3_s1_air_cleaner_model` | Air cleaner model |
| `sensor.laser3_s1_air_cleaner_speed` | Fan speed |
| `sensor.laser3_s1_air_cleaner_sensor_d` | Particle sensor D reading |
| `sensor.laser3_s1_air_cleaner_sensor_s` | Particle sensor S reading |
| `sensor.laser3_s1_pre_filter_remaining` | Pre-filter life remaining (%) |
| `sensor.laser3_s1_medium_efficiency_filter_remaining` | Medium efficiency filter life remaining (%) |
| `sensor.laser3_s1_activated_carbon_filter_remaining` | Activated carbon filter life remaining (%) |
| `sensor.laser3_s1_ultra_dense_carbon_mesh_filter_remaining` | Ultra dense carbon mesh filter life remaining (%) |
| `sensor.laser3_s1_high_efficiency_filter_remaining` | High efficiency filter life remaining (%) |

---

## 💬 Possible Status Values

### P2, F1, M1, D1

| Status | Meaning |
|--------|---------|
| `Running` | The laser is currently engraving |
| `Done` | The engraving job is finished |
| `Idle` | The machine is idle |
| `Sleep` | The device is in sleep mode |
| `Ready` | (M1 only) machine ready for work |
| `Unavailable` | Device offline or unreachable |
| `Unknown` | Unknown or invalid response |

### S1

| Status | Meaning |
|--------|---------|
| `Ready` | Machine ready for work |
| `Measuring` | Running auto-focus or measurement pass |
| `Starting` | Job is initializing |
| `Running` | The laser is currently engraving |
| `Finishing` | Job is wrapping up |
| `Idle` | The machine is idle |
| `Unavailable` | Device offline or unreachable |
| `Unknown` | Unknown or invalid response |

---

## 🤖 Example Automations

### 🔹 1. Turn on exhaust fan when Laser1 (F1) starts
```yaml
alias: Laser1 – Exhaust Fan
description: Turn on the exhaust fan when Laser1 (F1) starts engraving
triggers:
  - trigger: state
    entity_id: sensor.laser1_f1_status
actions:
  - choose:
      - conditions:
          - condition: state
            entity_id: sensor.laser1_f1_status
            state: Running
        sequence:
          - service: switch.turn_on
            target:
              entity_id: switch.exhaust_fan
    default:
      - service: switch.turn_off
        target:
          entity_id: switch.exhaust_fan
mode: single
```

### 🔹 2. Notify when Laser1 job is finished
```yaml
alias: Laser1 – Job Finished
description: Send a mobile notification when the engraving is done
triggers:
  - trigger: state
    entity_id: sensor.laser1_f1_status
    to: Done
actions:
  - service: notify.mobile_app_my_phone
    data:
      title: "xTool Laser1 – Job Completed"
      message: "Your engraving on the F1 is done ✅"
mode: single
```

### 🔹 3. Prevent blinds from closing while Laser2 (P2) is on
```yaml
alias: Blinds – Safe Close with Laser2 Check
description: Prevent blinds from closing if Laser2 (P2) is powered on
trigger:
  - platform: state
    entity_id: cover.living_room_blinds
    to: closing
condition:
  - condition: state
    entity_id: binary_sensor.laser2_p2_power
    state: "on"
action:
  - service: cover.stop_cover
    target:
      entity_id: cover.living_room_blinds
  - service: notify.mobile_app_my_phone
    data:
      message: "⚠️ Blinds closing blocked: Laser2 (P2) is currently powered ON."
mode: single
```

### 🔹 4. Notify when Laser3 (S1) AP2 filter needs replacing
```yaml
# NOTE: Adjust entity ID prefixes to match your device name from integration setup.
# Check Settings -> Devices -> your S1 device to confirm exact entity IDs.
alias: xTool AP2 - Filter Replacement Warning
description: >
  Persistent notification when any AP2 filter drops below 25% remaining.
  Critical alert when below 15%.

trigger:
  - platform: numeric_state
    entity_id: sensor.laser3_s1_pre_filter_remaining
    below: 25
    id: pre_filter
    variables:
      filter_name: "Pre-filter"

  - platform: numeric_state
    entity_id: sensor.laser3_s1_medium_efficiency_filter_remaining
    below: 25
    id: medium_filter
    variables:
      filter_name: "Medium Efficiency Filter"

  - platform: numeric_state
    entity_id: sensor.laser3_s1_activated_carbon_filter_remaining
    below: 25
    id: carbon_filter
    variables:
      filter_name: "Activated Carbon Filter"

  - platform: numeric_state
    entity_id: sensor.laser3_s1_ultra_dense_carbon_mesh_filter_remaining
    below: 25
    id: dense_carbon_filter
    variables:
      filter_name: "Ultra Dense Carbon Mesh Filter"

  - platform: numeric_state
    entity_id: sensor.laser3_s1_high_efficiency_filter_remaining
    below: 25
    id: hepa_filter
    variables:
      filter_name: "High Efficiency Filter"

action:
  - service: persistent_notification.create
    data:
      notification_id: "ap2_filter_{{ trigger.id }}"
      title: >
        {% if trigger.to_state.state | float < 15 %}
          Critical: AP2 Filter Replacement Required
        {% else %}
          AP2 Filter Replacement Warning
        {% endif %}
      message: >
        {% if trigger.to_state.state | float < 15 %}
          Critical:
        {% endif %}
        {{ filter_name }} is at {{ trigger.to_state.state }}% remaining.

mode: parallel
max: 5
```

### 🔹 5. Play an audio notification when Laser1 finishes
```yaml
alias: Laser1 – Audio Notification
description: Play a short audio clip when Laser1 (F1) completes a job
triggers:
  - trigger: state
    entity_id: sensor.laser1_f1_status
    to: Done
actions:
  - service: media_player.play_media
    target:
      entity_id: media_player.living_room_speaker
    data:
      media_content_id: "https://example.com/sounds/job_done.mp3"
      media_content_type: "music"
mode: single
```

## Support My Work
If you enjoy my projects or find them useful, consider supporting me on [Ko-fi](https://ko-fi.com/bassxt)!

[![Support me on Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/bassxt)

## Collaboration
If you work at xTool or are part of the development team —
I’d love to collaborate for extended testing, new model support, or official API insights 😉
Just reach out!
