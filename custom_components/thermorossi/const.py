"""Constants for the Thermorossi integration."""

DOMAIN = "thermorossi"
DEFAULT_SCAN_INTERVAL = 30

# Fast-poll schedule after a command: every 1s for 10s, then every 2s up to 30s
FAST_POLL_DELAYS = [*range(1, 11), *range(12, 32, 2)]
# Refresh-request debouncer cooldown (s); must not exceed the fast-poll step
REFRESH_COOLDOWN = 1.0

# API endpoints
API_GET_REGISTERS = "/ajax/get-registers"
API_SET_REGISTER = "/ajax/set-register"
API_GET_STATUS = "/ajax/get-status"  # Network state and module firmware (fwVer)

# get-registers payloads
GET_PAYLOAD = "key=020&category=1"
GET_CHRONO_PAYLOAD = "key=020&category=2"  # Weekly schedule, registers 24–65
# The schedule rarely changes: read it at most this often (s)
CHRONO_REFRESH_INTERVAL = 600

# set-register command values (0x5A00 = ON, 0xA500 = OFF - bitwise complements)
CMD_ON = 23040   # 0x5A00
CMD_OFF = 42240  # 0xA500
SET_KEY = "002"
SET_REG_ID = 1

# Register indices (within key=020, category=1)
REG_STATUS = 6       # Stove state (& 0xFF)
REG_SET_TEMP = 15    # Temperature setpoint: value * 0.25 - 18 °C (0x0F)
REG_AIR_TEMP = 16    # Measured ambient temp (room control module): value * 0.25 - 18 °C (0x10)
REG_FIRE_LEVEL = 12  # Power level 0–5 (0x0C)
REG_FAN_SPEED = 13   # Fan speed 1–6 (0x0D)
REG_PELLET = 10      # Pellet reserve: 0=OK, other=low/empty
REG_FLAGS = 7        # Flags register: bit0=chrono active, bit6=room control, bit7=eco mode
REG_FLUE_TEMP = 21   # Flue gas temperature (raw °C, direct value)
REG_RTC = 22         # Internal RTC clock: bits[13:11]=day(1-7), bits[10:6]=hour, bits[5:0]=minute
# Registers that must be present, or the firmware uses another layout
REQUIRED_REGISTERS = (REG_STATUS, REG_SET_TEMP, REG_AIR_TEMP)

# Weekly schedule (category=2): 6 registers per day starting Monday at 24,
# i.e. 3 slots of (start, stop), each encoded (hour << 8) | minute
REG_CHRONO_FIRST = 24
CHRONO_DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
CHRONO_SLOTS_PER_DAY = 3

# Temperature conversion: rawValue * TEMP_MUL + TEMP_OFFSET
TEMP_MUL = 0.25
TEMP_OFFSET = -18.0

# Stove status codes (register 6 & 0xFF)
STATUS_CODES = {
    0: "off",
    1: "off",
    2: "start",
    3: "work",
    4: "wait_on",
    5: "temp_ok",
    6: "no_prog",    # On but no schedule programmed ("NO PROGR.")
    7: "wait_time",
    8: "stop",       # Error / fault state
    9: "sunout",
}

# States considered "on" (stove is active/heating)
ACTIVE_STATES = {2, 3, 4, 5, 6}

# Distinct state keys exposed by the status sensor (ENUM options)
STATUS_OPTIONS = [*dict.fromkeys(STATUS_CODES.values()), "unknown"]

# Error state
ERROR_STATE = 8

# Alarm registers (32-bit code split across two 16-bit registers)
REG_ALARM_LSB = 8   # bits 0–15
REG_ALARM_MSB = 9   # bits 16–31

# HTTP headers for WiNET API requests
API_HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded",
    "X-Requested-With": "XMLHttpRequest",
}

# Alarm bit → translation key (from WiNET JS source)
ALARM_CODES = {
    0:  "no_pellets",
    1:  "start_failed",
    2:  "flue_gas_blocked",
    3:  "max_temp",
    4:  "flue_probe_disconnected",
    5:  "exhaust_fan_rpm",
    6:  "exhaust_fan_fault",
    7:  "seismic",
    8:  "probe_s1_disconnected",
    9:  "probe_s2_disconnected",
    10: "probe_acs_disconnected",
    11: "probe_sta_disconnected",
    12: "cleaning_motor",
    13: "ash_drawer_full",
    14: "ash_drawer_missing",
    15: "lcd_timeout",
    16: "probe_stg_disconnected",
}

# State keys exposed by the alarm message sensor (ENUM options)
ALARM_OPTIONS = ["ok", *ALARM_CODES.values(), "unknown"]

# ---------------------------------------------------------------------------
# "params" dialect (WiNET firmware 0.79 and others)
#
# get-registers answers a short "params" list of [id, value] pairs instead of
# the "registers" map, with other ids, scale factors given in the reply and a
# toggle command for on/off. Decoding taken from the module's management.js;
# see WINET_API.md.
# ---------------------------------------------------------------------------
DIALECT_REGISTERS = "registers"
DIALECT_PARAMS = "params"

# Payload read by the official page (category 4, the clock tab, returns the same set)
PARAMS_GET_PAYLOAD = "key=020&category=2"
# On/off is a TOGGLE: never send it without knowing the stove state
PARAMS_TOGGLE_PAYLOAD = "key=022"
# Module settings (tempDiv, setTempDiv, numPower, custom), read once by the
# official page; firmware 0.43 sends them only here, not with the values
PARAMS_SETTINGS_PAYLOAD = "key=019"

PARAM_AIR_TEMP = 0     # Ambient temperature: value * tempDiv °C
PARAM_STATUS = 2       # Stove state (PARAMS_STATUS_CODES)
PARAM_ALARM = 3        # Alarm bit field (PARAMS_ALARM_CODES), meaningful in alarm states
PARAM_SET_TEMP = 50    # Setpoint: value * setTempDiv °C, written with memory=1
PARAM_POWER = 51       # Power level 1..numPower, written with memory=1
PARAM_RTC_DAY = 59     # Stove clock: weekday 1-7 (1 = Monday)
PARAM_RTC_HOUR = 60    # Stove clock: hour, BCD
PARAM_RTC_MINUTE = 61  # Stove clock: minute, BCD
PARAMS_REQUIRED = (PARAM_STATUS, PARAM_SET_TEMP, PARAM_POWER)

# Setpoint range of the official page, in °C (the page divides it by
# setTempDiv to get the raw bounds)
PARAMS_SET_TEMP_MIN = 5
PARAMS_SET_TEMP_MAX = 40
PARAMS_DEFAULT_NUM_POWER = 5
# Divisor when the module sends none at all (firmware 0.43 answers key=019
# with {"result": false}): raw values are in half degrees there
PARAMS_DEFAULT_TEMP_DIV = 0.5
# Customization code (model variant) whose tables are decoded here; the page
# switches tables for about a hundred other codes
PARAMS_DEFAULT_CUSTOM = 65535

PARAMS_STATUS_CODES = {
    0: "off",
    1: "wait_flame",
    2: "wait_flame",
    3: "start",
    4: "work",
    5: "brazier_cleaning",
    6: "final_cleaning",
    7: "standby",
    8: "alarm",
    9: "alarm_memory",
}
PARAMS_STATUS_OPTIONS = [*dict.fromkeys(PARAMS_STATUS_CODES.values()), "unknown"]
PARAMS_OFF_STATE = 0
PARAMS_FINAL_CLEANING_STATE = 6
PARAMS_ERROR_STATES = {8, 9}
# A toggle sent less than this long ago (s) may not be reflected in the state yet
PARAMS_TOGGLE_GUARD = 15

# Alarm bit -> translation key (from the module's management.js)
PARAMS_ALARM_CODES = {
    0: "flue_probe_disconnected",
    1: "flue_overtemp",
    2: "exhaust_fan_fault",
    3: "start_failed",
    4: "no_pellets",
    5: "low_pressure",
    6: "thermal_safety",
    7: "pellet_door_open",
}
PARAMS_ALARM_OPTIONS = ["ok", *PARAMS_ALARM_CODES.values(), "unknown"]
