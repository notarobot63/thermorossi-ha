"""Constants for the Thermorossi integration."""

DOMAIN = "thermorossi"
DEFAULT_SCAN_INTERVAL = 30

# API endpoints
API_GET_REGISTERS = "/ajax/get-registers"
API_SET_REGISTER = "/ajax/set-register"

# get-registers payload
GET_PAYLOAD = "key=020&category=1"

# set-register command values (0x5A00 = ON, 0xA500 = OFF — bitwise complements)
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
    7: "wait_time",
    8: "stop",       # Error / fault state
    9: "sunout",
}

# States considered "on" (stove is active/heating)
ACTIVE_STATES = {2, 3, 4, 5}

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
