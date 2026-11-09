# Changelog

## [Unreleased]

### Documentation
- `WINET_API.md` and this changelog are now in English, and so are the GitHub release notes.

## [1.5.3]

### Fixed (`params` format, firmware 0.43)
- A response from the module settings (`key=019`) that is empty or has no divisor is no longer kept until restart: it is re-read on every poll, and temperatures are corrected as soon as the module returns its divisors.

## [1.5.2]

### Fixed (`params` format, firmware 0.43)
- Ambient temperature and setpoint displayed at twice the actual value (24 °C on the stove, 48 in Home Assistant, issue #2). Firmware 0.43 does not send the divisors (`tempDiv`, `setTempDiv`), nor `numPower` and `custom`, with the values: the integration now reads them once from the module settings (`key=019`), like the official page.

### Documentation
- README: firmware 0.43 supported, 0.79 confirmed on a real stove.

## [1.5.1]

### Fixed (`params` format, firmware 0.79)
- Setpoint: the range is 5 to 40 °C regardless of the step. On a half-degree stove (`setTempDiv` 0.5), it was wrongly limited to 2.5-20 °C.
- On/off: two simultaneous commands (an automation and the UI, for example) can no longer send two toggles that cancel each other out.
- On/off: an opposite request sent before the previous one is visible in the stove state is rejected with an error message, instead of being silently ignored.
- A module that reports a model variant (`custom`) other than the decoded one writes a warning to the log: its states and alarms may be misnamed.
- An inconsistent `numPower` in the module response can no longer result in a maximum power of 0.
- The error message for an unknown format now names both accepted formats (`registers` or `params`).

### Documentation
- README, *Firmware 0.79* section: read-only sensors disabled by default, setpoint and power unavailable during an alarm, missing entities to adapt in cards and automations, model variant, toggle behavior.

## [1.5.0]

### Added
- **Support for the `params` format** (WiNET firmware 0.79, issues #2 and #4). The module speaks another dialect of the API there, detected automatically on the first read. The same format is reported on firmwares 0.17 and 0.43: they should work too, without confirmation to date. Available entities: stove (on/off), state, ambient temperature, alarm message, alarm, stop on error, internal clock, adjustable setpoint and power. The decoding comes from the official module page script (`management.js`), cross-checked with a user recording.
  - On/off on this firmware is a toggle: the integration only sends it if it goes in the requested direction, and not a second time until the stove state has changed (15 s at most).
  - If the module firmware changes while Home Assistant is running, the integration reloads to recreate the right entities.

### Fixed
- Diagnostics: the WiFi network name returned by firmware 0.79 (`ssid`) is now redacted.

## [1.4.2]

### Documentation
- README: the unsupported `params` format is reported on firmwares 0.17, 0.43 and 0.79, and on brands other than Thermorossi (Stufe a Pellet Italia).
- README, *Unsupported firmware* section: how to recognize this format, what is already known about it (setpoint `50`, power `51`, on/off by toggle `key=022`), the information to include in an issue, and a more precise HAR capture procedure (page reload required, order of actions, capture during an alarm, HAR to zip).

## [1.4.1]

### Documentation
- README: *Supported firmware* section (0.73 supported, 0.79 not yet) with how to read the firmware version, and a consolidated and expanded *Troubleshooting* section: invalid address error, HAR capture procedure for an unsupported firmware, values that seem wrong (missing ambient temperature, schedule shifted by the stove clock, commands slow to apply, saturated module).
- README: the *Weekly schedule* sensor was missing from the entity list.
- Automation examples: notifications go through `notify.notify` (the Home Assistant default notifier) instead of a Signal `rest_command` to configure.
- `WINET_API.md`: new section on firmware 0.79 (`params` format, writing with `memory=1`, setpoint in `50`, power in `51`, on/off by toggle `key=022`) and a list of what remains to be clarified.

## [1.4.0]

### Added
- **Diagnostics** (*⋮ → Download diagnostics*): WiNET firmware version, raw module responses and decoded registers, without the IP address or the WiFi network name. They remain available when the integration no longer starts after a firmware update.

### Fixed
- When the WiNET module responds in an unknown format (reported on firmware 0.79), the log now shows the full response instead of its first 300 characters, along with the firmware version.
- No more deprecation warning at startup: device lookup uses `async_get_device_by_identifier` when Home Assistant provides it (the old call will stop working in 2027.8).
- A firmware that does return a register list, but without the state, setpoint or ambient temperature, is rejected with a message naming its version, instead of showing wrong values.

### Documentation
- The integration is now part of the HACS default catalog: the README Installation section simply says to search for "Thermorossi" in HACS, without adding a custom repository.

## [1.3.0]

### Added
- **"Weekly schedule" sensor** (diagnostic): it exposes the stove's time program, until now invisible from Home Assistant. Its value is the number of slots scheduled in the week, and each day is an attribute containing its slots in the `06:00-08:30` format.
  - The schedule is re-read only every 10 minutes, since it almost never changes.
  - If this read fails, only this sensor becomes unavailable: the other entities are not affected.
  - Slots are evaluated by the stove's internal clock, not the network clock. A clock that has drifted shifts the whole schedule. The "Internal clock" sensor lets you check it.

### Documentation
- `WINET_API.md`: the time program, service statistics and factory parameters are documented, the register map is completed (firmware versions, hydro model probes), and a section lists what remains unclear.
- Fix: raw register reading takes the `startAddr` and `nPoints` parameters (the names given so far returned an error that looked like an access denial).
- Network configuration documented: WiFi state, restart and firmware update (`status.html` page), WiFi scan and connection (`networks.html`), DHCP or static IP (`dhcp.html`), with the actual parameters of each endpoint.

> **Correction.** The first version of these notes claimed that the WiFi and DHCP endpoints were absent from the firmware. That was false: they are served by pages accessible from the WI-FI tab, which the initial analysis had not followed. The documentation was corrected after the 1.3.0 release, with no change to the integration.

## [1.2.1]

### Added
- Integration icon (`brand/icon.png`) shipped directly with the integration: it appears in Home Assistant 2026.3+ and in HACS. It is also a prerequisite for entering the HACS default list.

### Internal
- HACS validation in CI runs without exceptions (the icon check is no longer ignored).

## [1.2.0]

⚠️ **Home Assistant 2024.11 minimum required** (instead of 2024.1 announced until now, which was already wrong: 1.1.0 crashed below 2024.4).

### Fixed
- **English entity names**: the `translations/en.json` file was missing. For any installation that was neither French nor Italian, entities had no name (all "Thermorossi", `sensor.thermorossi_2`, `_3`...) and the configuration form had no labels.
- **Fast refresh after a command**: it did not work. The coordinator debouncer limited re-reads to one every 10 s instead of every second. It now also applies after a change to power, fan or setpoint, not only after on/off.
- **Ambient and flue temperatures**: they stayed "available" with their last value when the stove stopped responding. They now become unavailable like the other entities.
- **Stop on error**: the switch is no longer greyed out in the `stop` state. It appears "on" and turning it off sends the OFF command, which acknowledges the alarm (like the stove button). Turning it back on is refused until the alarm is acknowledged.
- **IPv6 addresses**: they were accepted but produced an invalid URL. They are now wrapped in brackets.
- **Native Lovelace card**: the alarm banners showed the template code instead of the message, because `tile` cards do not interpret templates. A card for the temperature setpoint was also added.
- **Alarm messages**: the Bubble card and automations show the translated message (`state_translated`) instead of the raw key (`no_pellets`...).
- **Missing registers**: `number` entities report "unknown" instead of inventing a value (0 or 1) when a register is missing.

### Configuration
- **Diagnosing the "Unexpected response from stove" error**: it is replaced by three explicit errors.
  - *HTTP error*: another device is responding at this IP.
  - *Not a WiNET module*: the response is not JSON.
  - *Unexpected data*: unknown firmware.

  Each failure is also detailed in the Home Assistant logs (HTTP status and start of the response). The README has a "Troubleshooting" section.
- **Reconfiguration**: you can change the stove IP address (*⋮ → Reconfigure*) without deleting the integration. Entities, history and automations are kept.
- The form re-displays the entered address after an error. The address is normalized (spaces, uppercase, IPv6 brackets).

### Entities
- The **State** and **Alarm message** sensors are *enum* sensors: they offer a list of possible values in the automation editor.
- **Internal clock**: the state is now `HH:MM`, and the day is in the `weekday` attribute (1 = Monday). It used to be "Mon 14:05", hardcoded in French. ⚠️ *Format change.*
- **Internal clock** and **Flue temperature** are classified as *diagnostic*.
- The read-only **Power**, **Fan speed** and **Setpoint** sensors, which duplicate the sliders, are disabled by default. This only affects new installations.
- Icons are declared in `icons.json` (state icon depending on the stove state). The old `icons.json` was not valid.

### Internal
- Reads and writes to the WiNET module are serialized by a single lock.
- The device is identified by the entry ID instead of the IP. The existing device is migrated automatically, without duplicates.
- `manifest.json`: keys sorted (required by hassfest), `integration_type` and `issue_tracker` added.
- Home Assistant tests (config flow, entities, fast refresh, stop on error, migration) and GitHub Actions CI (hassfest, HACS validation, tests).
- GitHub releases are published automatically from this file when a `vX.Y.Z` tag is pushed.

### Documentation
- README: entity table completed (flue, clock, timer, `no_prog` state), power range corrected (0-5), FR/EN entity_id mapping, Bubble card dependencies (Mushroom, card-mod).
- Compatibility with Piazzetta, Nordica, Extraflame and Edilkamin has never been tested: it is removed from the README.
- Automations use current HA syntax (`triggers:` / `actions:`).
- `WINET_API.md` documents writing registers 12, 13 and 15.

## [1.1.0]

### Added
- New `number` entity for the temperature setpoint (7-30 °C, 0.5 °C step)
- Flue temperature, internal RTC clock, active timer sensors + FR automations

### Fixed
- Inconsistent state icon on the "no schedule" state (no_prog)
- More robust register parsing (malformed payloads, non-numeric values)
- Register writes secured by lock, fast-poll cleanup on unload
- `number` entities decoupled and safeguards in case of error state

## [1.0.0]

First public version: local control via the WiNET HTTP API, switch,
state sensor, power/fan sliders, error, alarm and pellet sensors,
English/French/Italian translations.