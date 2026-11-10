# Contexte pour Claude Code

Pôle P4 de l'équipe ECE Paris au concours DroneLoad 2027 (Planète Sciences, C'Space). Le pôle P4 couvre la navigation sans GPS, la machine à états de mission (`/mission`), le lancement des nœuds au démarrage et la simulation SITL.

## Matériel

- Châssis Holybro X500 V2, contrôleur de vol Pixhawk 6X sous ArduPilot Copter 4.7.2.
- Ordinateur compagnon Raspberry Pi 5, relié à la Pixhawk en MAVLink 2 par UART.
- Optical flow et télémètre ToF (H-Flow, DroneCAN) fusionnés par l'EKF3 de la Pixhawk.

## Logiciel

- Ubuntu 24.04, ROS 2 Jazzy, MAVROS installé par apt, ArduPilot SITL au tag `Copter-4.7.2`.
- `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp` sur toutes les machines.
- Vol commandé en GUIDED par MAVROS : `set_mode`, `cmd/arming`, `cmd/takeoff`, puis consignes de position ou de vitesse.
- Sans GPS, l'origine EKF doit être fixée avant tout ordre GUIDED.
- Navigation sans GPS en SITL : `sim_vehicle.py` sans Gazebo, car avec Gazebo le télémètre simulé renvoie NaN en 4.7.2.

## État au 11/11/2026

Structure et documentation seulement. Le paquet `droneload_mission` n'est pas encore dans le dépôt. Le drone n'a pas volé.

## Règles

- Ne rien présenter comme testé ou validé s'il ne l'a pas été. Distinguer : écrit, testé hors ROS, testé en SITL, testé en vol.
- Ne pas inventer de valeur de paramètre, de référence de composant ou de résultat. Demander.
- Le contrat `/vision/cible` est dans `docs/interface-vision-mission.md`. Le modifier avant le code, jamais après.
- Tout changement de paramètre ArduPilot passe par un fichier `.parm` versionné.
- Le dépôt est public : aucun secret, aucun identifiant Wi-Fi.
- Rédaction en français, phrases courtes, chaque choix technique suivi de sa raison.
