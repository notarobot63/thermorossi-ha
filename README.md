# Thermorossi WiNET - Home Assistant Integration

> **🤖 Vibe Coded with Claude**
> This project was built through an AI-assisted development session with [Claude](https://claude.ai) (Anthropic).
> It is shared as-is, without warranty of any kind. Test thoroughly before relying on it for anything critical.
>
> Remember: if you don't like projects coded with AI help don't use them ;-)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
![HA min version](https://img.shields.io/badge/HA-2024.11%2B-blue)
![Languages](https://img.shields.io/badge/languages-EN%20%7C%20FR%20%7C%20IT-green)

Local polling integration for **Thermorossi** pellet stoves equipped with the **WiNET** WiFi module (Micronova).

> Only tested on a Thermorossi stove (WiNET firmware 0.73). Other brands using a Micronova-based WiNET module may work but are **untested** - feedback welcome.

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

---

## Installation

### Via HACS (recommended)

The integration is not (yet) in the HACS default store: add it as a custom repository.

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=notarobot63&repository=thermorossi-ha&category=integration)

Or manually:

1. Open **HACS**, then **⋮** (top right) → **Custom repositories**
2. Repository: `https://github.com/notarobot63/thermorossi-ha`, Type: **Integration** → **Add**
3. Search for **Thermorossi WiNET** in HACS and **Download** it
4. Restart Home Assistant

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

### Troubleshooting setup errors

| Error | Meaning |
|-------|---------|
| *Unable to connect* | Nothing answers at this address: wrong IP, stove powered off, or WiNET not on the network. |
| *HTTP error* | A device answers but returns an HTTP error. Usually the IP of another device (router, box, NAS…). Open `http://<IP>/management.html` in a browser: it must show the WiNET page. |
| *Not a WiNET module* | A device answers, but not with the WiNET API (HTML page…). Check the IP. |
| *Unexpected data* | The WiNET module answers, but in a format this integration does not know (other firmware?). |

The exact HTTP status and the beginning of the reply are written to the Home
Assistant log (*Settings → System → Logs*, search `thermorossi`). When opening
an issue, please include that log line and the output of:

```bash
curl -i -X POST -H "X-Requested-With: XMLHttpRequest" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "key=020&category=1" http://<IP>/ajax/get-registers
```

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
> Notifications use `rest_command.signal_notify` (Signal via SignalMe) by default - adapt to your setup (`notify.mobile_app_*`, `notify.ntfy`, etc.). See the header comment in `automations.yaml` for the required `rest_command` config.

---

## Protocol

- **Transport**: HTTP (local network only, no TLS - WiNET firmware limitation)
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
