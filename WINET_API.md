# Thermorossi WiNET - Documentation technique API

Résultat d'une session de rétro-ingénierie du module WiFi WiNET embarqué sur les poêles à
pellets Thermorossi. L'analyse repose sur l'inspection du trafic HTTP et du code JavaScript
servi par le module (`/js/management.js`, `/js/networks.js`, `/js/dhcp.js`).

---

## Le module WiNET

- **Matériel** : ESP32 ou similaire, serveur HTTP embarqué
- **Rôle** : pont entre le bus Modbus interne du poêle et une interface web/HTTP
- **Interface web** : `http://<ip>/management.html`
- **Adresse par défaut** : DHCP (IP fixe recommandée sur le routeur)
- **Firmware testé** : 0.73

Le module est un **proxy mince** : il lit les registres Modbus du board principal et les expose
via HTTP. Il ne stocke pas lui-même les valeurs - elles viennent du poêle.

---

## Endpoints HTTP

Toutes les requêtes sont des `POST` avec `Content-Type: application/x-www-form-urlencoded`
et le header `X-Requested-With: XMLHttpRequest`.

### Lecture de registres

```
POST /ajax/get-registers
```

Le paramètre `key` détermine le mode de lecture :

| key | Description |
|-----|-------------|
| `020` | Lecture par catégorie (`category=1/2/3`) |
| `030` | Lecture par plage (`startRegId=N&regCount=N`) |
| `010` | Lecture du programme horaire |

Réponse :
```json
{"registers": [[index, value], [index, value], ...]}
```

**Catégories (key=020) :**

| category | Contenu |
|----------|---------|
| 1 | Registres temps-réel (état, températures, alarmes…) |
| 2 | Programme horaire (7 jours × créneaux allumage/extinction) |
| 3 | Informations firmware (84 registres ASCII, index 128-211) |

### Écriture d'un registre

```
POST /ajax/set-register
Body: key=002&regId=N&value=N&result=false
```

Réponse : `{"result": true}` ou `{"result": false}`

### Écriture multiple (programme horaire)

```
POST /ajax/set-registers
Body: key=003 à 009  (un par jour : lundi=003 … dimanche=009)
```

### Commandes principales

```
POST /ajax/set-register
Body: key=002&regId=1&value=23040&result=false   → Allumage (0x5A00)
Body: key=002&regId=1&value=42240&result=false   → Extinction (0xA500)
```

Les deux valeurs sont des compléments binaires l'une de l'autre.

### Chrono (programme horaire on/off)

```
POST /ajax/get-registers
Body: key=021&value=1    → activer le chrono
Body: key=021&value=0    → désactiver le chrono
```

### Renommer le poêle

```
POST /ajax/get-registers
Body: key=051&name=MonPoele
```

### Authentification

```
POST /ajax/login
Body: key=login&pin=XXXX

POST /ajax/logout
Body: key=logout
```

Réponse login : `{"logged": true, "type": 1}` ou `{"logged": false, "type": 0}`

Le serveur maintient **une seule session globale** (pas de sessions par client). Une
connexion authentifiée affecte tous les clients simultanés.

---

## Carte des registres (category=1)

| Index | Nom | Format | Notes |
|-------|-----|--------|-------|
| 0 | - | - | |
| 1 | Commande | word | Écriture : 0x5A00=ON, 0xA500=OFF |
| 3 | Flags modèle | flags | bit2=Air ARM, bit13=WiFi, bit6=room control |
| 6 | État | `& 0xFF` | Voir codes état ci-dessous |
| 7 | Flags | flags | bit0=chrono actif, bit6=room control, bit7=eco |
| 8 | Alarme LSB | word | Bits d'alarme 0–15 |
| 9 | Alarme MSB | word | Bits d'alarme 16–31 |
| 10 | Pellets | word | 0=OK, autre=réserve basse/vide |
| 11 | Mode opération | word | |
| 12 | Niveau puissance | 0–5 | Niveau de flamme actuel |
| 13 | Vitesse ventilateur | 1–6 | Vitesse ventilateur actuelle |
| 15 | Consigne température | raw | `valeur × 0,25 − 18` = °C |
| 16 | Température ambiante | raw | `valeur × 0,25 − 18` = °C (module room control) |
| 21 | Température fumées | raw °C | Valeur directe en degrés Celsius |
| 22 | Horloge RTC | encodé | bits[13:11]=jour(1-7), bits[10:6]=heure, bits[5:0]=minute |

**Conversion température** (reg 15 et 16) :
```
temp_celsius = raw_value × 0.25 − 18.0
```

**Décodage RTC** (reg 22) :
```
jour    = (val >> 11) & 0x7     # 1=Lun … 7=Dim
heure   = (val >> 6)  & 0x1F
minute  = val         & 0x3F
```

---

## Codes d'état (reg[6] & 0xFF)

| Valeur | Code | Description |
|--------|------|-------------|
| 0, 1 | `off` | Éteint |
| 2 | `start` | Allumage en cours |
| 3 | `work` | Chauffe |
| 4 | `wait_on` | En attente d'allumage |
| 5 | `temp_ok` | Température atteinte |
| 6 | `no_prog` | Actif mais sans programme horaire |
| 7 | `wait_time` | Attente du créneau horaire |
| 8 | `stop` | Arrêt sur erreur |
| 9 | `sunout` | Arrêt estival |

---

## Codes d'alarme (reg[8] + reg[9], 32 bits)

L'alarme est un champ de bits sur 32 bits. Chaque bit correspond à une alarme distincte.
Plusieurs alarmes peuvent être actives simultanément.

| Bit | Code | Description |
|-----|------|-------------|
| 0 | `no_pellets` | Pas de pellets / nettoyer brûleur |
| 1 | `start_failed` | Démarrage échoué / nettoyer brûleur |
| 2 | `flue_gas_blocked` | Fumées non évacuées / vérifier conduit |
| 3 | `max_temp` | Alarme température maximale |
| 4 | `flue_probe_disconnected` | Sonde température fumées déconnectée |
| 5 | `exhaust_fan_rpm` | Capteur RPM extracteur fumées |
| 6 | `exhaust_fan_fault` | Défaut ventilateur fumées |
| 7 | `seismic` | Alarme sismique |
| 8 | `probe_s1_disconnected` | Sonde S1 déconnectée |
| 9 | `probe_s2_disconnected` | Sonde S2 déconnectée |
| 10 | `probe_acs_disconnected` | Sonde ACS déconnectée |
| 11 | `probe_sta_disconnected` | Sonde STA déconnectée |
| 12 | `cleaning_motor` | Défaut moteur nettoyage |
| 13 | `ash_drawer_full` | Tiroir à cendres plein |
| 14 | `ash_drawer_missing` | Tiroir à cendres absent |
| 15 | `lcd_timeout` | Timeout LCD |
| 16 | `probe_stg_disconnected` | Sonde STG déconnectée |

---

## Authentification PIN

Le module expose 3 niveaux d'accès PIN, protégeant des sections de l'interface web :

| Type | Niveau | Débloque |
|------|--------|---------|
| 1 | Tech support | Langue de l'interface, statistiques board |
| 2 | Factory | Tests I/O, réglages usine (reg 256+) |
| 3 | Debug | Browser Modbus brut (reg 0–898) |

**PIN confirmé :** `1230` → type=1 (tech support)

Les types 2 et 3 n'ont pas de PIN valide dans la plage 0000–9999 (brute force exhaustif).
Le PIN est comparé de façon **exacte sur 4 caractères** (ni préfixe, ni suffixe).

**Limitation :** les registres tech (177–194 : compteurs de démarrages, heures de
fonctionnement…) sont stockés sur le board principal. Le module WiFi ne les reçoit que si
le poêle est en mode service, accessible uniquement depuis l'écran LCD physique.

---

## Configuration WiFi

### Lire l'état WiFi

```
POST /ajax/get-registers
Body: key=020&category=1
```

Puis dans la réponse, le JSON contient aussi : `rssi`, `authLevel`, `name`.

### Scan des réseaux disponibles

```
GET /ajax/get-networks
```

### Connexion à un réseau

```
POST /ajax/connect
Body: ssid=MonReseau&password=motdepasse
```

### Configuration IP

```
GET  /ajax/get-dhcp
POST /ajax/set-dhcp
Body: dhcpEnabled=true|false&staticIp=x.x.x.x&staticMask=x.x.x.x&staticGw=x.x.x.x
```

---

## Exemple : lecture complète de l'état

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

## Limites connues

- **Session globale** : une seule session active côté serveur. Un login depuis un client
  affecte tous les autres. À prendre en compte pour l'automatisation.
- **Registres tech vides** : les statistiques du board (heures de fonctionnement, compteur
  de démarrages…) ne sont pas exposées sans interaction physique avec le poêle.
- **Pas de WebSocket** : le module ne fait que du polling HTTP. L'interface web poll toutes
  les 500 ms.
- **Résistance au brute force** : au-delà de ~20 req/s, le module devient injoignable
  pendant quelques secondes (protection implicite par saturation, pas de ban IP).
