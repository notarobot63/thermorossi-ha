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

STATUS_LABELS = {
    "off":       "Éteint",
    "start":     "Allumage",
    "work":      "Chauffe",
    "wait_on":   "En attente",
    "temp_ok":   "Temp. OK",
    "wait_time": "Attente horaire",
    "stop":      "Arrêt (erreur)",
    "sunout":    "Arrêt estival",
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

# Alarm bit messages (from WiNET JS source)
ALARM_MESSAGES = {
    0:  "Pas de pellets / Nettoyer brûleur",
    1:  "Démarrage échoué / Nettoyer brûleur",
    2:  "Fumées non évacuées / Vérifier conduit",
    3:  "Alarme température max",
    4:  "Sonde température fumées déconnectée",
    5:  "Capteur RPM extracteur fumées",
    6:  "Alarme ventilateur fumées",
    7:  "Alarme sismique",
    8:  "Sonde S1 déconnectée",
    9:  "Sonde S2 déconnectée",
    10: "Sonde ACS déconnectée",
    11: "Sonde STA déconnectée",
    12: "Moteur nettoyage",
    13: "Tiroir plein",
    14: "Tiroir absent",
    15: "Timeout LCD",
    16: "Sonde STG déconnectée",
}
