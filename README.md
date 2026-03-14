# Thermorossi WiNET — Intégration Home Assistant

Intégration locale pour les poêles à granulés **Thermorossi** équipés du module WiFi **WiNET** (Micronova).
Compatible également avec d'autres marques utilisant le même module : Piazzetta, Nordica, etc.

## Fonctionnalités

| Entité | Type | Description |
|--------|------|-------------|
| Poêle | Switch | Allumer / Éteindre |
| État | Sensor | OFF / Allumage / Chauffe / Arrêt erreur... |
| Consigne température | Sensor | Température cible (°C) |
| Température ambiante | Sensor | Temp. mesurée par le module room control (si installé) |
| Niveau de puissance | Sensor | 0–5 |
| Vitesse ventilateur | Sensor | 1–6 |
| Erreur | Binary Sensor | Actif si le poêle est en état STOP |
| Pellets insuffisants | Binary Sensor | Actif si la réserve pellets est vide |

## États du poêle

| Code | État | Description |
|------|------|-------------|
| 1 | Éteint (OFF) | Poêle en veille |
| 2 | Allumage (START) | Allumage en cours |
| 3 | Chauffe (WORK) | Fonctionnement normal |
| 4 | En attente (WAIT ON) | En attente de conditions |
| 5 | Temp. OK | Température atteinte |
| 7 | Attente horaire | Chrono : pas encore l'heure |
| 8 | **Arrêt erreur (STOP)** | ⚠️ Vérifier brûleur ou pellets |
| 9 | Arrêt estival | Extinction estivale |

## Installation

### Via HACS (recommandé)

1. Ajouter ce dépôt comme source personnalisée HACS
2. Installer "Thermorossi WiNET"
3. Redémarrer Home Assistant

### Manuelle

Copier le dossier `custom_components/thermorossi/` dans votre répertoire `config/custom_components/`.

## Configuration

1. Aller dans **Paramètres → Appareils & Services → Ajouter une intégration**
2. Rechercher **Thermorossi**
3. Entrer l'adresse IP de votre poêle (ex: `192.168.1.36`)

## Automatisations recommandées

### Alerte erreur (brûleur / pellets)

```yaml
automation:
  - alias: "Thermorossi - Alerte erreur"
    trigger:
      - platform: state
        entity_id: binary_sensor.thermorossi_erreur
        to: "on"
    action:
      - service: notify.signal  # ou ntfy, mobile_app...
        data:
          message: "⚠️ Poêle en erreur — vérifier brûleur ou pellets"

  - alias: "Thermorossi - Pellets vides"
    trigger:
      - platform: state
        entity_id: binary_sensor.thermorossi_pellets_insuffisants
        to: "on"
    action:
      - service: notify.signal
        data:
          message: "⚠️ Réserve pellets vide"

  - alias: "Thermorossi - Allumage bloqué (brûleur encrassé)"
    trigger:
      - platform: state
        entity_id: sensor.thermorossi_etat
        to: "Allumage"
        for:
          minutes: 25
    action:
      - service: notify.signal
        data:
          message: "⚠️ Poêle bloqué en allumage depuis 25 min — brûleur à vérifier"
```

## Protocole

- **API** : HTTP locale sur le module WiNET (Micronova)
- **Polling** : toutes les 30 secondes
- **Aucune dépendance cloud**
- Commandes : `POST /ajax/set-register` avec valeurs `23040` (ON) et `42240` (OFF)
  (complément bit-à-bit : `0x5A00` ↔ `0xA500` — protocole de sécurité industriel)
