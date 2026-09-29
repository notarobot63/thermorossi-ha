# Changelog

## [1.3.0]

### Ajouts
- **Capteur « Programme hebdomadaire »** (diagnostic) : il expose le programme horaire du poêle, jusqu'ici invisible depuis Home Assistant. Sa valeur est le nombre de créneaux programmés dans la semaine, et chaque jour est un attribut contenant ses créneaux au format `06:00-08:30`.
  - Le programme est relu toutes les 10 minutes seulement, car il ne change quasiment jamais.
  - Si cette lecture échoue, seul ce capteur devient indisponible : les autres entités ne sont pas affectées.
  - Les créneaux sont évalués par l'horloge interne du poêle, pas par celle du réseau. Une horloge qui a dérivé décale tout le programme. Le capteur « Horloge interne » permet de le vérifier.

### Documentation
- `WINET_API.md` : le programme horaire, les statistiques de service et les paramètres d'usine sont documentés, la carte des registres est complétée (versions de firmware, sondes des modèles hydro), et une section liste ce qui reste non élucidé.
- Correction : la lecture brute de registres prend les paramètres `startAddr` et `nPoints` (les noms donnés jusqu'ici renvoyaient une erreur qui ressemblait à un refus d'accès).
- Configuration réseau documentée : état WiFi, redémarrage et mise à jour du firmware (page `status.html`), scan et connexion WiFi (`networks.html`), DHCP ou IP fixe (`dhcp.html`), avec les paramètres réels de chaque endpoint.

> **Rectificatif.** La première version de ces notes affirmait que les endpoints WiFi et DHCP étaient absents du firmware. C'était faux : ils sont servis par des pages accessibles depuis l'onglet WI-FI, que l'analyse initiale n'avait pas suivies. La documentation a été corrigée après la publication de la 1.3.0, sans changement de l'intégration.

## [1.2.1]

### Ajouts
- Icône de l'intégration (`brand/icon.png`) fournie directement avec l'intégration : elle s'affiche dans Home Assistant 2026.3+ et dans HACS. C'est aussi un prérequis pour entrer dans la liste par défaut de HACS.

### Interne
- La validation HACS de la CI tourne sans exception (la vérification des icônes n'est plus ignorée).

## [1.2.0]

⚠️ **Home Assistant 2024.11 minimum requis** (au lieu de 2024.1 annoncé jusqu'ici, qui était déjà faux : la 1.1.0 plantait en dessous de 2024.4).

### Corrections
- **Noms des entités en anglais** : le fichier `translations/en.json` manquait. Pour toute installation qui n'était ni en français ni en italien, les entités n'avaient pas de nom (toutes « Thermorossi », `sensor.thermorossi_2`, `_3`…) et le formulaire de configuration n'avait pas de libellés.
- **Rafraîchissement rapide après une commande** : il ne fonctionnait pas. Le debouncer du coordinator limitait les relectures à une toutes les 10 s au lieu de chaque seconde. Il s'applique maintenant aussi après un changement de puissance, de ventilation ou de consigne, pas seulement après on/off.
- **Températures ambiante et fumées** : elles restaient « disponibles » avec leur dernière valeur quand le poêle ne répondait plus. Elles passent maintenant en indisponible comme les autres entités.
- **Arrêt sur erreur** : l'interrupteur n'est plus grisé dans l'état `stop`. Il apparaît « allumé » et l'éteindre envoie la commande OFF, qui acquitte l'alarme (comme le bouton du poêle). Le rallumer est refusé tant que l'alarme n'est pas acquittée.
- **Adresses IPv6** : elles étaient acceptées mais produisaient une URL invalide. Elles sont maintenant entourées de crochets.
- **Carte Lovelace native** : les bannières d'alarme affichaient le code du template au lieu du message, car les cartes `tile` n'interprètent pas les templates. Une carte pour la consigne de température a aussi été ajoutée.
- **Messages d'alarme** : la carte Bubble et les automatisations affichent le message traduit (`state_translated`) au lieu de la clé brute (`no_pellets`…).
- **Registres absents** : les entités `number` renvoient « inconnu » au lieu d'inventer une valeur (0 ou 1) quand un registre est absent.

### Configuration
- **Diagnostic de l'erreur « Réponse inattendue du poêle »** : elle est remplacée par trois erreurs explicites.
  - *Erreur HTTP* : un autre appareil répond à cette IP.
  - *Pas un module WiNET* : la réponse n'est pas du JSON.
  - *Données inattendues* : firmware inconnu.

  Chaque échec est aussi détaillé dans les journaux de Home Assistant (statut HTTP et début de la réponse). Le README a une section « Troubleshooting ».
- **Reconfiguration** : on peut changer l'adresse IP du poêle (⋮ → Reconfigurer) sans supprimer l'intégration. Entités, historique et automatisations sont conservés.
- Le formulaire réaffiche l'adresse saisie après une erreur. L'adresse est normalisée (espaces, majuscules, crochets IPv6).

### Entités
- Les capteurs **État** et **Message alarme** sont des capteurs *enum* : ils proposent une liste des valeurs possibles dans l'éditeur d'automatisations.
- **Horloge interne** : l'état vaut maintenant `HH:MM`, et le jour est dans l'attribut `weekday` (1 = lundi). Avant, c'était « Lun 14:05 », figé en français. ⚠️ *Changement de format.*
- **Horloge interne** et **Température fumées** sont classées en *diagnostic*.
- Les capteurs en lecture seule **Puissance**, **Vitesse ventilateur** et **Consigne**, qui doublonnent les curseurs, sont désactivés par défaut. Cela ne concerne que les nouvelles installations.
- Les icônes sont déclarées dans `icons.json` (icône de l'état selon l'état du poêle). L'ancien `icons.json` n'était pas valide.

### Interne
- Les lectures et les écritures vers le module WiNET sont sérialisées par un seul verrou.
- L'appareil est identifié par l'ID de l'entrée et non plus par l'IP. L'appareil existant est migré automatiquement, sans doublon.
- `manifest.json` : clés triées (exigé par hassfest), `integration_type` et `issue_tracker` ajoutés.
- Tests Home Assistant (config flow, entités, rafraîchissement rapide, arrêt sur erreur, migration) et CI GitHub Actions (hassfest, validation HACS, tests).
- Les releases GitHub sont publiées automatiquement depuis ce fichier quand un tag `vX.Y.Z` est poussé.

### Documentation
- README : tableau des entités complété (fumées, horloge, chrono, état `no_prog`), plage de puissance corrigée (0–5), correspondance des entity_id FR/EN, dépendances de la carte Bubble (Mushroom, card-mod).
- La compatibilité Piazzetta, Nordica, Extraflame et Edilkamin n'a jamais été testée : elle est retirée du README.
- Les automatisations utilisent la syntaxe HA actuelle (`triggers:` / `actions:`).
- `WINET_API.md` documente l'écriture des registres 12, 13 et 15.

## [1.1.0]

### Ajouts
- Nouvelle entité `number` pour la consigne de température (7-30°C, pas de 0,5°C)
- Capteurs température fumées, horloge RTC interne, chrono actif + automatismes FR

### Corrections
- Icône d'état incohérente sur l'état "sans programme" (no_prog)
- Parsing des registres plus robuste (payloads malformés, valeurs non numériques)
- Écritures de registre sécurisées par verrou, nettoyage du fast-poll au déchargement
- Entités `number` découplées et garde-fous en cas d'état erreur

## [1.0.0]

Première version publique : pilotage local via l'API HTTP WiNET, interrupteur,
capteur d'état, curseurs puissance/ventilation, capteurs d'erreur, d'alarme et
de pellets, traductions anglais/français/italien.
