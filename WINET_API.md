# Thermorossi WiNET - Documentation technique API

Résultat de sessions de rétro-ingénierie du module WiFi WiNET embarqué sur les poêles à
pellets Thermorossi. L'analyse repose sur l'inspection du trafic HTTP et du code servi par
le module :

| Page | Script | Contenu |
|------|--------|---------|
| `management.html` | `management.js` | Pilotage du poêle, programme horaire, sections protégées par PIN. La page porte la table de décodage des registres dans les attributs de ses éléments |
| `status.html` | `status.js` | Onglet « WI-FI » : état réseau, redémarrage, mise à jour du firmware |
| `networks.html` | `networks.js` | Scan des réseaux WiFi et connexion (bouton de `status.html`) |
| `dhcp.html` | `dhcp.js` | DHCP ou IP fixe (bouton de `status.html`) |

`main.min.js` regroupe jQuery et la fonction de traduction commune. Les pages ne sont
reliées que par des navigations en JavaScript (`App.Utilities.GoToUrl`), pas par des liens.

Sauf mention contraire, tout ce qui suit a été vérifié sur un module réel. Les écritures
et les actions qui pourraient déconnecter le module sont documentées d'après le code de
l'interface, sans avoir été exécutées : c'est indiqué à chaque fois.

---

## Le module WiNET

- **Matériel** : puce Espressif, probablement un ESP8266 (les codes d'état WiFi 0–5
  reprennent l'énumération du SDK ESP8266). Serveur HTTP embarqué `NetSoftware-httpd/0.4`
- **Chemins inconnus** : le serveur ferme la connexion sans réponse HTTP
- **Rôle** : pont entre le bus Modbus interne du poêle et une interface web/HTTP
- **Interface web** : `http://<ip>/management.html`
- **Adresse par défaut** : DHCP (IP fixe recommandée sur le routeur)
- **Firmware testé** : 0.73

Le module est un **proxy mince** : il lit les registres Modbus du board principal et les expose
via HTTP. Il ne stocke pas lui-même les valeurs - elles viennent du poêle.

---

## Endpoints HTTP

Les requêtes sont des `POST` avec `Content-Type: application/x-www-form-urlencoded`
et le header `X-Requested-With: XMLHttpRequest`, sauf `GET /ajax/get-dhcp`. Les endpoints
réseau sont décrits dans [Configuration WiFi](#configuration-wifi).

### Lecture de registres

```
POST /ajax/get-registers
```

Le paramètre `key` détermine le mode de lecture :

| key | Description |
|-----|-------------|
| `020` | Lecture par catégorie (`category=1/2/3`) |
| `030` | Lecture brute par plage (`startAddr=N&nPoints=N`, voir ci-dessous) |

Réponse :
```json
{"registers": [[index, value], [index, value], ...]}
```

**Catégories (key=020) :**

| category | Contenu |
|----------|---------|
| 1 | Registres temps-réel (état, températures, alarmes…) |
| 2 | Programme horaire, registres 24–65 (voir [Programme horaire](#programme-horaire-category2)) |
| 3 | Informations firmware (84 registres ASCII, index 128-211) |

**Lecture brute (key=030) :**

```
POST /ajax/get-registers
Body: key=030&startAddr=177&nPoints=18
```

- `nPoints` est plafonné à 125 par requête, `startAddr + nPoints` doit rester ≤ 1024.
- **Aucune authentification n'est requise** : toute la plage 0–1023 est lisible sans PIN.
- Les noms de paramètres sont stricts : `startRegId`/`regCount` renvoient simplement
  `{"result": false}`, ce qui ressemble à un refus d'accès mais n'en est pas un.
- Réponse : `{"key": 30, "registers": [[index, value], ...]}`.

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

La copie du programme d'un jour sur un autre passe par `key=010` (paramètres `src` et `dest`).

### Commandes principales

```
POST /ajax/set-register
Body: key=002&regId=1&value=23040&result=false   → Allumage (0x5A00)
Body: key=002&regId=1&value=42240&result=false   → Extinction (0xA500)
```

Les deux valeurs sont des compléments binaires l'une de l'autre.

### Réglages écrits par l'intégration

L'intégration écrit aussi les registres suivants via le même endpoint
(`key=002&regId=N&value=N&result=false`), avec le même index qu'en lecture :

| regId | Réglage | Valeur écrite |
|-------|---------|---------------|
| 12 | Niveau de puissance | 0–5 |
| 13 | Vitesse ventilateur | 1–6 |
| 15 | Consigne température | `(°C + 18) / 0,25` (7–30 °C) |

Le module répond `{"result": true}` quand l'écriture est acceptée.

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
| 4 | Version firmware afficheur | word | 0 si l'afficheur ne la publie pas |
| 5 | Version firmware carte de puissance | word | idem |
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
| 17–20 | Sondes hydro | °C direct | Modèles hydro (eau chaudière, eau sanitaire…). ~99–100 sur un modèle air : sondes absentes |
| 21 | Température fumées | raw °C | Valeur directe en degrés Celsius |
| 22 | Horloge RTC | encodé | bits[13:11]=jour(1-7), bits[10:6]=heure, bits[5:0]=minute |
| 112 | Consigne hydro | °C direct | Plage 65–73 °C, modèles hydro uniquement |

L'interface web décode chaque registre à partir d'attributs portés par le HTML
(`reg`, `regType`, `mul`, `offset`, `mask`, `shift`, `unit`, `min`, `max`) : la table
de décodage est déclarative dans `management.html`, pas dans le JavaScript.

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

## Programme horaire (category=2)

Registres 24 à 65 : 6 registres par jour, du lundi au dimanche, soit 3 créneaux de
(allumage, extinction). Adresse du jour N (1 = lundi) : `24 + 6 × (N − 1)`.

| Décalage dans le jour | Contenu |
|-----------------------|---------|
| +0 / +1 | Créneau 1 : allumage / extinction |
| +2 / +3 | Créneau 2 : allumage / extinction |
| +4 / +5 | Créneau 3 : allumage / extinction |

Encodage d'un horaire : `(heure << 8) | minute` (ex. `0x081E` = 08:30). Un créneau dont
l'allumage égale l'extinction (typiquement `0`/`0`) est inutilisé.

Les créneaux sont évalués par l'horloge interne du poêle (reg 22), pas par l'heure du
réseau : une horloge dérivée décale tout le programme.

---

## Registres de service et d'usine

Lisibles via `key=030`, mais **toujours à 0** tant que le poêle n'est pas en mode service
(activé depuis l'écran LCD) : le board ne les pousse pas au module WiFi en temps normal.

Statistiques (177–194). Les compteurs sur deux registres forment un mot de 32 bits,
registre N = poids fort, N+1 = poids faible :

| Registres | Libellé firmware | Signification |
|-----------|------------------|---------------|
| 177 | MAIN HZ. | Fréquence secteur |
| 178–179 | SMOKE FAN SPEED | Vitesse extracteur de fumées |
| 180 | COCLEA ON | Vis sans fin (temps de marche) |
| 181–182 | NR. START TOT. | Nombre total d'allumages |
| 183–184 | NR. START CHRONO | Allumages par le programme horaire |
| 185–186 | NR. START EXT. | Allumages par commande externe |
| 187–188 | WORK HOUR TOT. | Heures de fonctionnement |
| 189–190 | COCLEA HOUR TOT. | Heures de vis sans fin |
| 191–192 | T SMOKE | Température fumées |
| 193–194 | T BOARD | Température carte |

Paramètres d'usine (220, 256–287) : test I/O (256), désactivation encodeur/sonde fumées
(257, 258), vitesses du ventilateur d'ambiance par niveau (259–265, 220), vitesses
extracteur (266–274), temps de marche vis sans fin par niveau (275–280), PID (281–282),
temporisations et seuils d'alarme (283–287). Ce sont des réglages de combustion :
**ne jamais les écrire**.

---

## Codes d'état (reg[6] & 0xFF)

| Valeur | Code | Description |
|--------|------|-------------|
| 0, 1 | `off` | Éteint (0 = `----` dans le firmware : état non encore reçu du board) |
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
| 3 | Debug | Browser Modbus brut de l'interface (l'API `key=030` sous-jacente, elle, répond sans PIN) |

**PIN confirmé :** valeur retirée de ce document public (firmware partagé entre poêles, un PIN divulgué ici serait valide ailleurs). Type=1 (tech support) a un PIN valide sur 4 chiffres, gardé en note privée.

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

La réponse porte, à côté de `registers` : `rssi`, `authLevel`, `name`, `localWeb` et `cat`.

Aucune des pages réseau ne demande de PIN dans l'interface. `get-status` et `get-dhcp`
répondent sans session.

### État réseau détaillé

```
POST /ajax/get-status
```

Vérifié. Réponse :

```json
{"status": 5, "lastDisconnectReason": 2, "currentIp": "192.168.1.100",
 "currentMask": "255.255.255.0", "currentGw": "192.168.1.1", "client": 3,
 "network": "MonReseau", "rssi": -67, "fwVer": "0.73", "boot": 2}
```

| Champ | Contenu |
|-------|---------|
| `status` | Connexion WiFi : 0 inactive, 1 en cours, 2 mauvais mot de passe, 3 point d'accès introuvable, 4 échec, 5 connecté avec IP |
| `client` | Connexion au cloud : 0 inactive, 1 en pause, 2 connecté, 3 non connecté |
| `lastDisconnectReason` | Code de déconnexion WiFi Espressif (1–24, 200–204) |
| `network`, `rssi` | SSID et signal en dBm |
| `currentIp`, `currentMask`, `currentGw` | Adressage en cours |
| `fwVer` | Version du firmware du module |

### Redémarrage et mise à jour du firmware

Documenté d'après `status.js`, **non exécuté**.

```
POST /ajax/reboot          → {"result": true}, le module redémarre
POST /ajax/upgrade         (sans corps) le module télécharge lui-même son firmware
POST /ajax/check-upg-sts   → {"flag": 1} en cours, {"flag": 2} terminé
```

`upgrade` n'envoie aucun fichier : le module va chercher la mise à jour sur internet.
Un poêle bloqué vers internet ne peut donc pas être mis à jour par ce biais.

### Scan des réseaux et connexion

Documenté d'après `networks.js`, **non exécuté** : le scan accepte une option de
reconnexion et une connexion change de réseau, deux opérations qui peuvent couper le
module du réseau en cours.

```
POST /ajax/get-networks    reconnect=…
     → {"available": [...], "network": "<SSID actuel>"}
POST /ajax/connect         network=MonReseau&password=motdepasse
     → {"connected": true} ou {"error": "…"}
```

### Configuration IP

```
GET  /ajax/get-dhcp
     → {"dhcpEnabled": 1, "staticIp": "0.0.0.0", "staticMask": "0.0.0.0", "staticGw": "0.0.0.0"}
POST /ajax/set-dhcp        dhcpEnabled=1|0&staticIp=…&staticMask=…&staticGw=…
     → {"result": true} ou {"error": "…"}
```

`get-dhcp` est vérifié. `set-dhcp` est documenté d'après `dhcp.js`, **non exécuté**.
Quand `dhcpEnabled=1`, l'interface renvoie les adresses statiques déjà stockées sans les
modifier.

Une page de réglages `settings.html` est prévue par l'interface, mais son bouton est
commenté dans `status.html` et la page n'existe pas sur ce firmware.

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
- **Verrouillage purement côté client** : le niveau d'accès renvoyé par `/ajax/login` ne
  sert qu'à afficher un conteneur déjà présent dans la page (`techParamsContainer`,
  `factoryParamsContainer`, `debugParamsContainer`). Le contenu de ces sections est servi
  à tout le monde, et `key=030` lit les registres correspondants sans authentification.

---

## Points non élucidés

- **Registres sans signification connue** : 0 (constant à `0x8000`), 2, 14, 23, et les
  valeurs du registre 11 (« mode opération »). Le registre 3 n'a que 3 bits identifiés
  sur 16. Le code du module ne traite explicitement que les registres 0, 3, 6–13, 16 et 22.
- **Registre 21 (température des fumées)** : aucun code du module ne le manipule. Son sens
  vient de l'observation, pas du firmware.
- **Créneaux 2 et 3 du programme horaire** : leur décodage vient du code du module, mais
  n'a jamais été observé sur un programme réel qui les utilise.
- **Écriture des registres d'usine** : on ignore si elle exige une session authentifiée.
  Non testé volontairement (paramètres de combustion).
- **Registres 66–127, 195–219, 221–255 et 288–1023** : lisibles, constamment à zéro.
