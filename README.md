# Thermorossi WiNET — Home Assistant Integration

> **🤖 Vibe Coded with Claude**
> This project was built through an AI-assisted development session with [Claude](https://claude.ai) (Anthropic).
> It is shared as-is, without warranty of any kind. Test thoroughly before relying on it for anything critical.

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
![HA min version](https://img.shields.io/badge/HA-2024.1%2B-blue)
![Languages](https://img.shields.io/badge/languages-EN%20%7C%20FR%20%7C%20IT-green)

Local polling integration for **Thermorossi** pellet stoves equipped with the **WiNET** WiFi module (Micronova).

> Also compatible with other brands using the same Micronova WiNET module: **Piazzetta**, **Nordica**, **Extraflame**, **Edilkamin**, and others.

No cloud. No account. Direct HTTP communication on your local network.

---

## Features

| Entity | Platform | Description |
|--------|----------|-------------|
| Stove | `switch` | Turn the stove on / off |
| State | `sensor` | Current operating state |
| Temperature setpoint | `sensor` | Target temperature (°C) |
| Ambient temperature | `sensor` | Room temperature from control module (if installed) |
| Power level | `sensor` | Read-only power level (0–5) |
| Fan speed | `sensor` | Read-only fan speed (1–6) |
| Alarm message | `sensor` | First active alarm, or "OK" |
| Error stop | `binary_sensor` | Active when stove is in STOP/fault state |
| Alarm | `binary_sensor` | Active when any alarm bit is set (with `active_alarms` attribute) |
| Pellets low | `binary_sensor` | Active when pellet reserve sensor reports empty |
| Power level | `number` | Adjustable power level (1–5) |
| Fan speed | `number` | Adjustable fan speed (1–6) |

### Stove states

| Key | Description |
|-----|-------------|
| `off` | Standby |
| `start` | Ignition in progress |
| `work` | Heating |
| `wait_on` | Waiting for conditions |
| `temp_ok` | Target temperature reached |
| `wait_time` | Scheduled standby (timer) |
| `stop` | ⚠️ Error stop — check burner or pellets |
| `sunout` | Summer shutdown |

---

## Requirements

- Home Assistant 2024.1 or later
- Thermorossi (or compatible) pellet stove with the **WiNET WiFi module** connected to your local network
- The stove's local IP address (assign a static DHCP lease for reliability)

---

## Installation

### Via HACS (recommended)

1. In HACS, go to **Integrations → ⋮ → Custom repositories**
2. Add `https://github.com/notarobot63/thermorossi-ha` as an **Integration**
3. Search for **Thermorossi WiNET** and install
4. Restart Home Assistant

### Manual

1. Copy `custom_components/thermorossi/` into your HA config directory under `custom_components/`
2. Restart Home Assistant

---

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Thermorossi**
3. Enter your stove's IP address (e.g. `192.168.1.36`)

The integration will verify connectivity before saving. If it fails, check that the stove is powered on and reachable on your network.

---

## Lovelace cards

Two ready-to-use card configurations are included:

### Bubble Card (requires [Bubble Card](https://github.com/Clooos/Bubble-Card))

`lovelace-card.yaml` — Compact card with state sub-buttons and conditional alarm banner.

### Native HA tiles (no custom cards required)

`lovelace-card-native.yaml` — 100% native HA tile cards, works without any HACS frontend dependency.

---

## Automations

`automations.yaml` contains 7 example automations:

| # | Trigger | Description |
|---|---------|-------------|
| 1 | Any alarm bit set | General alarm notification |
| 2 | Error stop (STOP state) | Stove fault notification |
| 3 | Pellets low sensor | Refill reminder |
| 4 | Stuck in `start` for 25 min | Clogged burner warning |
| 5 | Unexpected shutdown during heating | Pellets exhausted / fault detection |
| 6 | Transition to `work` | Ignition success confirmation |
| 7 | All alarms cleared | Recovery notification |

> Notifications use `notify.ntfy` by default — adapt to your setup (`notify.mobile_app_*`, `notify.signal`, etc.).

---

## Protocol

- **Transport**: HTTP (local network only, no TLS — WiNET firmware limitation)
- **Polling interval**: 30 seconds (background), 1 s × 10 + 2 s × 10 after commands
- **API**: `POST /ajax/get-registers` and `POST /ajax/set-register`
- **ON/OFF values**: `23040` (0x5A00) and `42240` (0xA500) — bitwise complements (industrial safety pattern)
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

Pull requests are welcome. To add a new language, copy `translations/fr.json` to `translations/<lang>.json` and translate the values.

---

## License

MIT
