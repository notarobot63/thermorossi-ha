# Thermorossi WiNET - Technical API Documentation

Result of reverse-engineering sessions of the WiNET WiFi module embedded in Thermorossi pellet stoves. The analysis is based on inspection of the HTTP traffic and of the code served by the module:

| Page | Script | Content |
|------|--------|---------|
| `management.html` | `management.js` | Stove control, schedule program, PIN-protected sections. The page carries the register decoding table in the attributes of its elements |
| `status.html` | `status.js` | "WI-FI" tab: network status, restart, firmware update |
| `networks.html` | `networks.js` | WiFi network scan and connection (button on `status.html`) |
| `dhcp.html` | `dhcp.js` | DHCP or static IP (button on `status.html`) |

`main.min.js` bundles jQuery and the shared translation function. The pages are linked only through JavaScript navigations (`App.Utilities.GoToUrl`), not through links.

Unless stated otherwise, everything below was verified on a real module. Writes and actions that could disconnect the module are documented from the interface code, without having been executed: this is indicated each time.

---

## The WiNET module

- **Hardware**: Espressif chip, probably an ESP8266 (the WiFi status codes 0–5 match the ESP8266 SDK enumeration). Embedded HTTP server `NetSoftware-httpd/0.4`
- **Unknown paths**: the server closes the connection without an HTTP response
- **Role**: bridge between the stove's internal Modbus bus and a web/HTTP interface
- **Web interface**: `http://<ip>/management.html`
- **Default address**: DHCP (static IP recommended on the router)
- **Tested firmware**: 0.73. Firmware 0.79 speaks another dialect of the API, see [Firmware 0.79](#firmware-079-params-format) (supported, confirmed by users on 0.79 and 0.43, not tested by us)

The module is a **thin proxy**: it reads the Modbus registers of the main board and exposes them over HTTP. It does not store the values itself; they come from the stove.

---

## HTTP endpoints

Requests are `POST` with `Content-Type: application/x-www-form-urlencoded` and the header `X-Requested-With: XMLHttpRequest`, except `GET /ajax/get-dhcp`. The network endpoints are described in [WiFi configuration](#wifi-configuration).

### Reading registers

```
POST /ajax/get-registers
```

The `key` parameter determines the read mode:

| key | Description |
|-----|-------------|
| `020` | Read by category (`category=1/2/3`) |
| `030` | Raw read by range (`startAddr=N&nPoints=N`, see below) |

Response:
```json
{"registers": [[index, value], [index, value], ...]}
```

**Categories (key=020):**

| category | Content |
|----------|---------|
| 1 | Real-time registers (status, temperatures, alarms...) |
| 2 | Schedule program, registers 24–65 (see [Schedule program](#schedule-program-category2)) |
| 3 | Firmware information (84 ASCII registers, index 128-211) |

**Raw read (key=030):**

```
POST /ajax/get-registers
Body: key=030&startAddr=177&nPoints=18
```

- `nPoints` is capped at 125 per request, `startAddr + nPoints` must stay ≤ 1024.
- **No authentication is required**: the whole range 0–1023 is readable without a PIN.
- Parameter names are strict: `startRegId`/`regCount` simply return `{"result": false}`, which looks like an access denial but is not one.
- Response: `{"key": 30, "registers": [[index, value], ...]}`.

### Writing a register

```
POST /ajax/set-register
Body: key=002&regId=N&value=N&result=false
```

Response: `{"result": true}` or `{"result": false}`

### Multiple write (schedule program)

```
POST /ajax/set-registers
Body: key=003 to 009  (one per day: Monday=003 … Sunday=009)
```

Copying the program from one day to another goes through `key=010` (parameters `src` and `dest`).

### Main commands

```
POST /ajax/set-register
Body: key=002&regId=1&value=23040&result=false   → Power on (0x5A00)
Body: key=002&regId=1&value=42240&result=false   → Power off (0xA500)
```

The two values are bitwise complements of each other.

### Settings written by the integration

The integration also writes the following registers through the same endpoint (`key=002&regId=N&value=N&result=false`), with the same index as in reading:

| regId | Setting | Value written |
|-------|---------|---------------|
| 12 | Power level | 0–5 |
| 13 | Fan speed | 1–6 |
| 15 | Temperature setpoint | `(°C + 18) / 0.25` (7–30 °C) |

The module replies `{"result": true}` when the write is accepted.

### Chrono (on/off schedule program)

```
POST /ajax/get-registers
Body: key=021&value=1    → enable the chrono
Body: key=021&value=0    → disable the chrono
```

### Renaming the stove

```
POST /ajax/get-registers
Body: key=051&name=MyStove
```

### Authentication

```
POST /ajax/login
Body: key=login&pin=XXXX

POST /ajax/logout
Body: key=logout
```

Login response: `{"logged": true, "type": 1}` or `{"logged": false, "type": 0}`

The server maintains **a single global session** (no per-client sessions). An authenticated login affects all simultaneous clients.

---

## Register map (category=1)

| Index | Name | Format | Notes |
|-------|------|--------|-------|
| 0 | - | - | |
| 1 | Command | word | Write: 0x5A00=ON, 0xA500=OFF |
| 3 | Model flags | flags | bit2=Air ARM, bit13=WiFi, bit6=room control |
| 4 | Display firmware version | word | 0 if the display does not publish it |
| 5 | Power board firmware version | word | same |
| 6 | Status | `& 0xFF` | See status codes below |
| 7 | Flags | flags | bit0=chrono active, bit6=room control, bit7=eco |
| 8 | Alarm LSB | word | Alarm bits 0–15 |
| 9 | Alarm MSB | word | Alarm bits 16–31 |
| 10 | Pellets | word | 0=OK, other=low/empty reserve |
| 11 | Operating mode | word | |
| 12 | Power level | 0–5 | Current flame level |
| 13 | Fan speed | 1–6 | Current fan speed |
| 15 | Temperature setpoint | raw | `value × 0.25 − 18` = °C |
| 16 | Room temperature | raw | `value × 0.25 − 18` = °C (room control module) |
| 17–20 | Hydro probes | °C direct | Hydro models (boiler water, domestic water...). ~99–100 on an air model: probes absent |
| 21 | Flue gas temperature | raw °C | Direct value in degrees Celsius |
| 22 | RTC clock | encoded | bits[13:11]=day(1-7), bits[10:6]=hour, bits[5:0]=minute |
| 112 | Hydro setpoint | °C direct | Range 65–73 °C, hydro models only |

The web interface decodes each register from attributes carried by the HTML (`reg`, `regType`, `mul`, `offset`, `mask`, `shift`, `unit`, `min`, `max`): the decoding table is declarative in `management.html`, not in the JavaScript.

**Temperature conversion** (reg 15 and 16):
```
temp_celsius = raw_value × 0.25 − 18.0
```

**RTC decoding** (reg 22):
```
day     = (val >> 11) & 0x7     # 1=Mon … 7=Sun
hour    = (val >> 6)  & 0x1F
minute  = val         & 0x3F
```

---

## Schedule program (category=2)

Registers 24 to 65: 6 registers per day, from Monday to Sunday, i.e. 3 slots of (on, off). Address of day N (1 = Monday): `24 + 6 × (N − 1)`.

| Offset within the day | Content |
|-----------------------|---------|
| +0 / +1 | Slot 1: on / off |
| +2 / +3 | Slot 2: on / off |
| +4 / +5 | Slot 3: on / off |

Time encoding: `(hour << 8) | minute` (e.g. `0x081E` = 08:30). A slot whose on time equals its off time (typically `0`/`0`) is unused.

Slots are evaluated by the stove's internal clock (reg 22), not by network time: a drifted clock shifts the whole program.

---

## Service and factory registers

Readable via `key=030`, but **always at 0** as long as the stove is not in service mode (enabled from the LCD screen): the board does not push them to the WiFi module under normal conditions.

Statistics (177–194). Counters spanning two registers form a 32-bit word, register N = most significant, N+1 = least significant:

| Registers | Firmware label | Meaning |
|-----------|------------------|---------------|
| 177 | MAIN HZ. | Mains frequency |
| 178–179 | SMOKE FAN SPEED | Flue gas extractor speed |
| 180 | COCLEA ON | Auger (running time) |
| 181–182 | NR. START TOT. | Total number of ignitions |
| 183–184 | NR. START CHRONO | Ignitions by schedule program |
| 185–186 | NR. START EXT. | Ignitions by external command |
| 187–188 | WORK HOUR TOT. | Operating hours |
| 189–190 | COCLEA HOUR TOT. | Auger hours |
| 191–192 | T SMOKE | Flue gas temperature |
| 193–194 | T BOARD | Board temperature |

Factory parameters (220, 256–287): I/O test (256), encoder/flue gas probe disable (257, 258), room fan speeds per level (259–265, 220), extractor speeds (266–274), auger running times per level (275–280), PID (281–282), timings and alarm thresholds (283–287). These are combustion settings: **never write them**.

---

## Status codes (reg[6] & 0xFF)

| Value | Code | Description |
|--------|------|-------------|
| 0, 1 | `off` | Off (0 = `----` in the firmware: status not yet received from the board) |
| 2 | `start` | Ignition in progress |
| 3 | `work` | Heating |
| 4 | `wait_on` | Waiting for ignition |
| 5 | `temp_ok` | Temperature reached |
| 6 | `no_prog` | Active but without a schedule program |
| 7 | `wait_time` | Waiting for the time slot |
| 8 | `stop` | Stop on error |
| 9 | `sunout` | Summer shutdown |

---

## Alarm codes (reg[8] + reg[9], 32 bits)

The alarm is a 32-bit bit field. Each bit corresponds to a distinct alarm. Several alarms can be active at the same time.

| Bit | Code | Description |
|-----|------|-------------|
| 0 | `no_pellets` | No pellets / clean the burner |
| 1 | `start_failed` | Ignition failed / clean the burner |
| 2 | `flue_gas_blocked` | Flue gases not evacuated / check the duct |
| 3 | `max_temp` | Maximum temperature alarm |
| 4 | `flue_probe_disconnected` | Flue gas temperature probe disconnected |
| 5 | `exhaust_fan_rpm` | Flue gas extractor RPM sensor |
| 6 | `exhaust_fan_fault` | Flue gas fan fault |
| 7 | `seismic` | Seismic alarm |
| 8 | `probe_s1_disconnected` | Probe S1 disconnected |
| 9 | `probe_s2_disconnected` | Probe S2 disconnected |
| 10 | `probe_acs_disconnected` | ACS probe disconnected |
| 11 | `probe_sta_disconnected` | STA probe disconnected |
| 12 | `cleaning_motor` | Cleaning motor fault |
| 13 | `ash_drawer_full` | Ash drawer full |
| 14 | `ash_drawer_missing` | Ash drawer missing |
| 15 | `lcd_timeout` | LCD timeout |
| 16 | `probe_stg_disconnected` | STG probe disconnected |

---

## PIN authentication

The module exposes 3 PIN access levels, protecting sections of the web interface:

| Type | Level | Unlocks |
|------|--------|---------|
| 1 | Tech support | Interface language, board statistics |
| 2 | Factory | I/O tests, factory settings (reg 256+) |
| 3 | Debug | Raw Modbus browser of the interface (the underlying `key=030` API, however, responds without a PIN) |

**Confirmed PIN:** value removed from this public document (firmware shared between stoves, a PIN disclosed here would be valid elsewhere). Type=1 (tech support) has a valid 4-digit PIN, kept in a private note.

Types 2 and 3 have no valid PIN in the 0000–9999 range (exhaustive brute force). The PIN is compared **exactly on 4 characters** (no prefix, no suffix).

**Limitation:** tech registers (177–194: ignition counters, operating hours...) are stored on the main board. The WiFi module only receives them if the stove is in service mode, accessible only from the physical LCD screen.

---

## WiFi configuration

### Read WiFi state

```
POST /ajax/get-registers
Body: key=020&category=1
```

The response carries, alongside `registers`: `rssi`, `authLevel`, `name`, `localWeb` and `cat`.

None of the network pages asks for a PIN in the interface. `get-status` and `get-dhcp` respond without a session.

### Detailed network state

```
POST /ajax/get-status
```

Verified. Response:

```json
{"status": 5, "lastDisconnectReason": 2, "currentIp": "192.168.1.100",
 "currentMask": "255.255.255.0", "currentGw": "192.168.1.1", "client": 3,
 "network": "MyNetwork", "rssi": -67, "fwVer": "0.73", "boot": 2}
```

| Field | Content |
|-------|---------|
| `status` | WiFi connection: 0 inactive, 1 connecting, 2 wrong password, 3 access point not found, 4 failure, 5 connected with IP |
| `client` | Cloud connection: 0 inactive, 1 paused, 2 connected, 3 not connected |
| `lastDisconnectReason` | Espressif WiFi disconnect code (1–24, 200–204) |
| `network`, `rssi` | SSID and signal in dBm |
| `currentIp`, `currentMask`, `currentGw` | Current addressing |
| `fwVer` | Module firmware version |

### Reboot and firmware update

Documented from `status.js`, **not executed**.

```
POST /ajax/reboot          → {"result": true}, the module reboots
POST /ajax/upgrade         (no body) the module downloads its own firmware
POST /ajax/check-upg-sts   → {"flag": 1} in progress, {"flag": 2} finished
```

`upgrade` sends no file: the module fetches the update from the internet. A stove with no internet access therefore cannot be updated this way.

### Network scan and connection

Documented from `networks.js`, **not executed**: the scan accepts a reconnect option and a connection switches networks, two operations that can cut the module off from its current network.

```
POST /ajax/get-networks    reconnect=…
     → {"available": [...], "network": "<current SSID>"}
POST /ajax/connect         network=MyNetwork&password=secret
     → {"connected": true} or {"error": "…"}
```

### IP configuration

```
GET  /ajax/get-dhcp
     → {"dhcpEnabled": 1, "staticIp": "0.0.0.0", "staticMask": "0.0.0.0", "staticGw": "0.0.0.0"}
POST /ajax/set-dhcp        dhcpEnabled=1|0&staticIp=…&staticMask=…&staticGw=…
     → {"result": true} or {"error": "…"}
```

`get-dhcp` is verified. `set-dhcp` is documented from `dhcp.js`, **not executed**. When `dhcpEnabled=1`, the interface returns the already stored static addresses without modifying them.

The interface provides for a `settings.html` settings page, but its button is commented out in `status.html` and the page does not exist on this firmware.

---

## Example: full state read

```python
import urllib.request, json

url = "http://192.168.1.100/ajax/get-registers"
data = b"key=020&category=1"
headers = {
    "Content-Type": "application/x-www-form-urlencoded",
    "X-Requested-With": "XMLHttpRequest",
}

req = urllib.request.Request(url, data=data, headers=headers)
with urllib.request.urlopen(req, timeout=10) as r:
    payload = json.loads(r.read())

regs = {entry[0]: entry[1] for entry in payload["registers"]}

status_raw = regs.get(6, 0) & 0xFF
temp_set   = regs.get(15, 0) * 0.25 - 18.0
temp_air   = regs.get(16, 0) * 0.25 - 18.0
temp_flue  = regs.get(21, 0)          # direct °C
alarm_code = (regs.get(9, 0) << 16) | regs.get(8, 0)
chrono_on  = bool(regs.get(7, 0) & 0x1)
```

---

## Firmware 0.79 (`params` format)

Supported by the integration. Sources:

- two recordings (HAR) of the official interface (`management.html`) provided by users whose module runs 0.79. The second contains the page scripts (`management.js`), which is where the decoding table below comes from, along with a power-on, setpoint and power changes, then a shutdown;
- two public projects that control modules returning the same format:
  [jeffreybrits/Winet_Pellet_Stove](https://github.com/jeffreybrits/Winet_Pellet_Stove)
  and [DarkSario/invicta-lodi8-ha-integration](https://github.com/DarkSario/invicta-lodi8-ha-integration)
  (Invicta stove).

Nothing has been verified on a 0.79 module by us, but one user confirmed it works on their stove (issue #4). Firmware 0.43 speaks the same format, with a difference in the settings (see *Reading*), according to a user's diagnostics (issue #2).

### Reading

```
POST /ajax/get-registers
Body: key=020&category=2
```

The official interface queries `category=2` (and `category=4` on the clock tab, with the same content). On some modules, `category=1` returns an empty list. Instead of `registers`, the response carries a short list of `[id, value]` pairs:

```json
{
  "key": "020",
  "params": [[0,46],[2,0],[3,0],[4,4],[50,23],[51,3],[59,7],[60,22],[61,2],[62,8],
             [63,17],[64,38],[300,1],[301,128],[302,0],[303,0]],
  "cat": 2, "signal": 4, "logTemp": 230, "tempDiv": 0.5, "setTempDiv": 1,
  "numPower": 5, "mode": 0, "modeThreeshold": 0, "tStart": 22, "tStop": 24,
  "model": 0, "isOld": false, "custom": 65535, "name": "NO NAME",
  "tsense": {"show": 0, "list": []},
  "inetTime": [2026, 11, 8, 15, 57, 0, 0, 7]
}
```

(the real response also contains `ssid`, removed here). The numbers have nothing to do with the 0.73 register map.

The divisors `tempDiv` and `setTempDiv`, as well as `numPower` and `custom`, also come from `POST /ajax/get-registers` `key=019` (module settings, with the weekly schedule `mon` … `sun`), which the page reads on load. Firmware **0.43** only sends them there: its `key=020&category=2` response is limited to `params`, `cat`, `signal`, `bk`, `localWeb`, `authLevel`, `model` and `name`. Without them, temperature and setpoint come out doubled (`tempDiv` and `setTempDiv` are 0.5 on this stove). 0.43 also returns ids `10`, `11`, `12` (120, 10, 69 in the capture), unexplained.

`custom` is the model customization code: the page changes its display and tables for about a hundred codes. Everything below applies to the default branch (`65535`, the one in the captures).

### Decoding table

| id / field | Meaning | Decoding |
|------------|---------|----------|
| `0` | Ambient temperature | × `tempDiv` °C (46 × 0.5 = 23 °C) |
| `2` | Stove state | Table below |
| `3` | Alarms | Bit field below, shown only in states 8 and 9 |
| `50` | Setpoint | × `setTempDiv` °C, raw bounds 5 to 40 |
| `51` | Power | 1 to `numPower` |
| `59` | Stove clock: day of the week | 1 = Monday … 7 = Sunday |
| `60`, `61` | Stove clock: hour, minute | BCD (`0x16` = 16 h) |
| `62`, `63`, `64` | Stove clock: day, month, year | BCD, year + 2000 |
| `inetTime` | Local network date and time | `[year, month, day, h, min, s, ?, day of the week]` |

States (id `2`):

| Code | Official page | Key in the integration |
|------|---------------|------------------------|
| 0 | OFF | `off` |
| 1, 2 | ATTESA FIAMMA (waiting for flame) | `wait_flame` |
| 3 | ACCENSIONE (ignition) | `start` |
| 4 | LAVORO (work) | `work` |
| 5 | PULIZIA BRACIERE (brazier cleaning) | `brazier_cleaning` |
| 6 | PULIZIA FINALE (final cleaning) | `final_cleaning` |
| 7 | STAND-BY | `standby` |
| 8 | ALLARME | `alarm` |
| 9 | MEMORIA ALLARME (stored alarm) | `alarm_memory` |

In state 4, if the ambient temperature reaches the setpoint, the page displays "LAVORO (MODULA)" (internal code 200), with no value of its own in `params`.

Alarms (id `3`, first active bit displayed): bit 0 flue probe, 1 flue overheating, 2 extractor, 3 ignition failure, 4 no pellets, 5 lack of pressure, 6 thermal safety, 7 pellet hatch open. The value briefly goes to 4 at the start of an ignition without the stove being in alarm: the page only displays it in states 8 and 9.

### Writing

```
POST /ajax/set-register
Body: key=002&memory=1&regId=50&value=24
```

Same endpoint as in 0.73, with an extra `memory=1` parameter. The module responds `{"result":true}` and the next read reflects the new value.

### On / off

```
POST /ajax/get-registers
Body: key=022
```

Response `{"result":true}`. It is a **toggle**: the same command turns an off stove on and an on stove off. The official page offers "switch on" if the state is 0 and "switch off" otherwise, and refuses to switch on during final cleaning. Observed in the capture: 0 → command → 1 (2 s later) → 2, then command → 6.

The integration only sends it if it goes in the requested direction, and not a second time as long as the state has not changed since the previous one (15 s at most).

### Unresolved

- `4`: reads 4 to 6 in the capture, rises during final cleaning. The page calls it "flue temperature" (+30 °C) for other customization codes, but does not display it for `65535`.
- `302`, `303`: countdown of the current phase (`303` decreases by about one unit per second, restarts at 180 at the start of phase 2).
- `300`, `301`, `logTemp`, `mode`, `modeThreeshold`, `tStart`/`tStop`, `isOld`, `model`, `tsense` (wireless probes).

---

## Known limitations

- **Global session**: only one active session server-side. A login from one client affects all the others. To be taken into account for automation.
- **Empty tech registers**: board statistics (operating hours, start counter, etc.) are not exposed without physical interaction with the stove.
- **No WebSocket**: the module only does HTTP polling. The web interface polls every 500 ms.
- **Brute-force resistance**: above ~20 req/s, the module becomes unreachable for a few seconds (implicit protection by saturation, no IP ban).
- **Purely client-side locking**: the access level returned by `/ajax/login` only serves to display a container already present in the page (`techParamsContainer`, `factoryParamsContainer`, `debugParamsContainer`). The content of these sections is served to everyone, and `key=030` reads the corresponding registers without authentication.

---

## Unresolved points

- **Registers with no known meaning**: 0 (constant at `0x8000`), 2, 14, 23, and the values of register 11 ("operation mode"). Register 3 has only 3 bits identified out of 16. The module code only explicitly handles registers 0, 3, 6–13, 16 and 22.
- **Register 21 (flue temperature)**: no module code manipulates it. Its meaning comes from observation, not from the firmware.
- **Slots 2 and 3 of the weekly schedule**: their decoding comes from the module code, but has never been observed in a real schedule that uses them.
- **Writing factory registers**: it is unknown whether it requires an authenticated session. Deliberately not tested (combustion parameters).
- **Registers 66–127, 195–219, 221–255 and 288–1023**: readable, constantly zero.