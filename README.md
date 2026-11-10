# Thermorossi WiNET - Home Assistant Integration

> **🤖 Vibe Coded with Claude**
> This project was built through an AI-assisted development session with [Claude](https://claude.ai) (Anthropic).
> It is shared as-is, without warranty of any kind. Test thoroughly before relying on it for anything critical.
>
> Remember: if you don't like projects coded with AI help don't use them ;-)

[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/integration)
![HA min version](https://img.shields.io/badge/HA-2024.11%2B-blue)
![Languages](https://img.shields.io/badge/languages-EN%20%7C%20FR%20%7C%20IT-green)

Local polling integration for **Thermorossi** pellet stoves equipped with the **WiNET** WiFi module (Micronova).

> Developed on a Thermorossi stove (WiNET firmware 0.73); firmwares 0.79 and 0.43 confirmed working by users. Other brands using a Micronova-based WiNET module may work but are **untested** - feedback welcome. See [Supported firmware](#supported-firmware).

No cloud. No account. Direct HTTP communication on your local network.

---

## Features

| Entity | Platform | Description |
|--------|----------|-------------|
| Stove | `switch` | Turn the stove on / off (see *Error stop* below) |
| State | `sensor` | Current operating state (enum) |
| Ambient temperature | `sensor` | Room temperature from control module (only if installed) |
| Alarm message | `sensor` | First active alarm, or "OK" (enum) |
| Flue temperature | `sensor` | Flue gas temperature (°C) - diagnostic |
| Internal clock | `sensor` | Stove RTC clock `HH:MM`, `weekday` attribute (1 = Monday) - diagnostic |
| Weekly schedule | `sensor` | Number of programmed chrono slots, each weekday's `HH:MM-HH:MM` slots as attributes (refreshed every 10 min) - diagnostic |
| Temperature setpoint | `sensor` | Read-only setpoint - *disabled by default* (use the `number`) |
| Power level | `sensor` | Read-only power level - *disabled by default* (use the `number`) |
| Fan speed | `sensor` | Read-only fan speed - *disabled by default* (use the `number`) |
| Error stop | `binary_sensor` | Active when stove is in STOP/fault state |
| Alarm | `binary_sensor` | Active when any alarm bit is set (with `active_alarms` and `code` attributes) |
| Pellets low | `binary_sensor` | Active when pellet reserve sensor reports empty |
| Chrono active | `binary_sensor` | Active when the weekly schedule (chrono) is enabled |
| Power level | `number` | Adjustable power level (0–5) |
| Fan speed | `number` | Adjustable fan speed (1–6) |
| Temperature setpoint | `number` | Adjustable target temperature, 7–30 °C (0.5 °C steps) |

### Entity IDs

Entity IDs are generated from the entity names **in the language Home Assistant
uses when the integration is added**. The example automations and cards in this
repository use the French IDs:

| English | French |
|---------|--------|
| `switch.thermorossi_stove` | `switch.thermorossi_poele` |
| `sensor.thermorossi_state` | `sensor.thermorossi_etat` |
| `sensor.thermorossi_alarm_message` | `sensor.thermorossi_message_alarme` |
| `binary_sensor.thermorossi_alarm` | `binary_sensor.thermorossi_alarme` |
| `binary_sensor.thermorossi_error_stop` | `binary_sensor.thermorossi_arret_erreur` |
| `binary_sensor.thermorossi_pellets_low` | `binary_sensor.thermorossi_pellets_insuffisants` |
| `number.thermorossi_power_level` | `number.thermorossi_niveau_de_puissance` |
| `number.thermorossi_fan_speed` | `number.thermorossi_vitesse_ventilateur` |
| `number.thermorossi_temperature_setpoint` | `number.thermorossi_consigne_temperature` |

### Stove states

| Key | Description |
|-----|-------------|
| `off` | Standby |
| `start` | Ignition in progress |
| `work` | Heating |
| `wait_on` | Waiting for conditions |
| `temp_ok` | Target temperature reached |
| `no_prog` | On, but no schedule programmed |
| `wait_time` | Scheduled standby (timer) |
| `stop` | ⚠️ Error stop - check burner or pellets |
| `sunout` | Summer shutdown |

### Error stop

When the stove is in the `stop` error state, the **Stove** switch shows as *on*:
the alarm has not been acknowledged yet. Turning the switch **off** sends the
OFF command, which acknowledges the alarm (like the power button on the stove).
Turning it *on* is refused until the alarm has been acknowledged. The power,
fan and setpoint sliders are unavailable in this state.

---

## Requirements

- Home Assistant 2024.11 or later
- Thermorossi (or compatible) pellet stove with the **WiNET WiFi module** connected to your local network
- The stove's local IP address (assign a static DHCP lease for reliability)

### Supported firmware

The WiNET firmware version is shown in the module's web page (*WI-FI* tab) and
in the integration diagnostics. It can also be read with
`curl -X POST -H "X-Requested-With: XMLHttpRequest" http://<IP>/ajax/get-status`
(field `fwVer`).

| WiNET firmware | Status |
|----------------|--------|
| 0.73 | ✅ Supported (developed and tested on it) |
| 0.79 | ✅ Supported, with fewer entities: see [Firmware 0.79](#firmware-079). Decoded from the module's own web page and confirmed by a user on a real stove. |
| 0.43 | ✅ Supported, same entities as 0.79: confirmed by a user. Requires 1.5.4 or later (ambient temperature and setpoint were shown doubled before); this fix is not yet confirmed on a real stove. |
| 0.17 | Should work: reported with the same `params` format as 0.79, but nobody has confirmed it yet. Please report whether it works. |
| Other | Unknown. If setup works, all entities should behave as described; if not, please open an issue with the log line described below. |

The firmware number alone does not tell which API format a module speaks: a
hydro stove on 0.81 was reported with the classic `registers` format of 0.73.
The integration detects the format by itself at the first read.

### Firmware 0.79

Firmware 0.79 speaks another dialect of the WiNET API (a short `params` list
instead of the register map), also used by 0.43 and reported on 0.17 and on other
brands (e.g. Stufe a Pellet Italia). The integration detects it by itself and creates
only the entities this firmware provides:

| Entity | Notes |
|--------|-------|
| Stove (`switch`) | See below |
| State (`sensor`) | `off`, `wait_flame`, `start`, `work`, `brazier_cleaning`, `final_cleaning`, `standby`, `alarm`, `alarm_memory` |
| Ambient temperature (`sensor`) | |
| Alarm message (`sensor`), Alarm and Error stop (`binary_sensor`) | Only in the `alarm` and `alarm_memory` states, like the official page |
| Internal clock (`sensor`) | Diagnostic |
| Temperature setpoint, Power level (`number`) | Setpoint 5–40 °C, step taken from the module; power 1 to the module's maximum (5 on the tested stove). Unavailable in the `alarm` states |
| Temperature setpoint, Power level (`sensor`) | Read-only duplicates, *disabled by default* |

Fan speed, flue temperature, pellets, chrono and weekly schedule are not
available on this firmware: cards and automations that use them need adapting.

The module also reports a model variant (`custom` field). Only the default one
(65535) has been decoded; on another variant, states and alarms may be named
wrongly, and a warning is written to the log once. Please open an issue with a
recording of the module's web page (see [Unsupported firmware](#unsupported-firmware))
if that happens.

On/off is a single **toggle** command on this firmware. The integration only
sends it when it moves the stove the requested way: turning on a stove that
is not off, or turning off a stove that is off or in final cleaning, does
nothing. While a toggle has not yet shown in the stove state (up to 15 s), a
request in the same direction does nothing and the opposite one is refused, so
two quick commands cannot cancel each other. Turning on during the final
cleaning is refused, as on the official page. In the `alarm` states, turning
the switch off acknowledges the alarm.

---

## Installation

### Via HACS (recommended)

1. Open **HACS** and search for **Thermorossi**
2. Select **Thermorossi WiNET** and **Download** it
3. Restart Home Assistant

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=notarobot63&repository=thermorossi-ha&category=integration)

### Manual

1. Copy `custom_components/thermorossi/` into your HA config directory under `custom_components/`
2. Restart Home Assistant

---

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Thermorossi**
3. Enter your stove's IP address (e.g. `192.168.1.100`)

The integration will verify connectivity before saving.

If the stove's IP address changes later, use **⋮ → Reconfigure** on the
integration: entities, history and automations are kept.

---

## Troubleshooting

### Setup errors

| Error | Meaning |
|-------|---------|
| *Invalid host or IP address* | The value entered is not a valid hostname or IP address. Enter the address only, without `http://` or a path. |
| *Unable to connect* | Nothing answers at this address: wrong IP, stove powered off, or WiNET not on the network. |
| *HTTP error* | A device answers but returns an HTTP error. Usually the IP of another device (router, box, NAS…). Open `http://<IP>/management.html` in a browser: it must show the WiNET page. |
| *Not a WiNET module* | A device answers, but not with the WiNET API (HTML page…). Check the IP. |
| *Unexpected data* | The WiNET module answers, but in a format this integration does not know (other firmware?). The log line gives the WiNET firmware version and the full reply. |

The exact HTTP status and the reply are written to the Home Assistant log
(*Settings → System → Logs*, search `thermorossi`). When opening an issue,
please include that log line and the output of:

```bash
curl -i -X POST -H "X-Requested-With: XMLHttpRequest" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "key=020&category=1" http://<IP>/ajax/get-registers
```

### The integration stops working after a firmware update

Attach the diagnostics to your issue (*Settings → Devices & services →
Thermorossi → ⋮ → Download diagnostics*). They contain the firmware version and
the raw replies, with the IP address and WiFi name removed, and remain
available while the integration is retrying to start.

### Unsupported firmware

If setup fails with *Unexpected data*, your firmware speaks a different dialect
of the WiNET API, or a variant of the `params` format (see
[Firmware 0.79](#firmware-079)) that does not provide the stove state, setpoint
and power level (ids 2, 50 and 51) where the integration expects them. Its
meaning is defined in the module's own web page, which is why a recording of
that page is needed. What is known so far is in [WINET_API.md](WINET_API.md).

**1. Open an issue** with the WiNET firmware version, the stove brand and model,
and the full log line (*Settings → System → Logs*, entry from
`custom_components.thermorossi.config_flow`). It contains the firmware version
and the module's complete reply.

**2. Record the module's web page** (a HAR file):

1. Open `http://<IP>/management.html` in Chrome, Edge or Firefox.
2. Open the developer tools (`F12`), go to the **Network** tab and tick
   **Disable cache**.
3. **Reload the page** while the developer tools are open. This is essential:
   `management.html` and `management.js` contain the table that gives the
   meaning of each value, and they are only recorded if the page loads during
   the recording. A capture made without reloading only contains raw numbers.
4. In this order, waiting a few seconds between actions: turn the stove on,
   let it heat for a few minutes, change the setpoint, change the power level,
   then turn it off.
5. Right-click in the list of requests → **Save all as HAR**, then zip it
   (GitHub does not accept `.har` files directly).

If the stove ever shows an alarm or runs out of pellets, a short capture at that
moment (with a page reload) is just as useful: it shows how these states are
encoded. Also note, if you can, what the stove's display showed at each step.

The HAR contains your module's local IP address and WiFi network name. Share it
privately if you prefer, rather than attaching it to a public issue.

### Values that look wrong

| Symptom | Explanation |
|---------|-------------|
| *Ambient temperature* is unavailable | The stove only measures room temperature with the optional room control module. Without it, the value is unavailable. |
| The weekly schedule fires on the wrong day or at the wrong time | The stove applies its schedule with its own clock (*Internal clock* sensor, `weekday` attribute: 1 = Monday), not with Home Assistant's. If that clock or its weekday has drifted, set it again on the stove's display. |
| A command seems to have no effect | The module accepts commands immediately, but the stove takes a few seconds to apply them. After any command the integration polls every 1-2 s for about 30 s, then every 30 s. |
| The module stops answering for a few seconds | Above roughly 20 requests per second the module saturates. Avoid running other tools that poll it in a tight loop alongside the integration. |

---

## Lovelace cards

Two ready-to-use card configurations are included:

### Bubble Card (requires [Bubble Card](https://github.com/Clooos/Bubble-Card), [Mushroom](https://github.com/piitaya/lovelace-mushroom) and [card-mod](https://github.com/thomasloven/lovelace-card-mod))

`lovelace-card.yaml` - Compact card with state sub-buttons and conditional alarm banner.

### Native HA tiles (no custom cards required)

`lovelace-card-native.yaml` - 100% native HA tile cards, works without any HACS frontend dependency.

---

## Automations

`automations.yaml` contains 4 example automations:

| # | Trigger | Description |
|---|---------|-------------|
| 1 | Any alarm bit set | General alarm notification |
| 2 | Error stop (STOP state) | Stove fault notification |
| 3 | Pellets low sensor | Refill reminder |
| 4 | `start` → `stop` transition | Stuck/clogged ignition warning |

> The automations and cards use the French entity IDs - see [Entity IDs](#entity-ids).
>
> Notifications use `notify.notify` (your default notifier) - replace it with the service you use (`notify.mobile_app_*`, `notify.ntfy`, etc.).

---

## Protocol

- **Transport**: HTTP (local network only, no TLS - WiNET firmware limitation)
- **Full API notes**: [WINET_API.md](WINET_API.md), written against firmware 0.73, and a section on the `params` format of firmwares 0.79 and 0.43 (decoding table, toggle command, settings reply)
- **Polling interval**: 30 seconds (background), 1 s × 10 + 2 s × 10 after any command (on/off, power, fan, setpoint)
- **API**: `POST /ajax/get-registers` and `POST /ajax/set-register`
- **ON/OFF values**: `23040` (0x5A00) and `42240` (0xA500) - bitwise complements (industrial safety pattern)
- **No cloud dependency**, no Thermorossi account required

---

## Languages

| Language | Status |
|----------|--------|
| English | ✅ Default |
| French | ✅ `translations/fr.json` |
| Italian | ✅ `translations/it.json` |

Entity names, stove states, alarm messages and config flow errors are fully translated.

---

## Contributing

Pull requests are welcome. To add a new language, copy `translations/en.json` to `translations/<lang>.json` and translate the values.
`strings.json` is the English source: keep `translations/en.json` identical to it.

Run the tests with:

```bash
pip install -r requirements_test.txt
pytest
```

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

---

## License

MIT
