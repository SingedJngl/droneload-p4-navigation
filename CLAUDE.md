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

- Avec Gazebo, le SITL vole au GPS simulé : il sert au terrain, aux caméras et à la logique de mission, pas à l'estimation de position.

## État au 13/11/2026

- Le terrain du règlement V0.1 existe en simulation Gazebo (`sitl/gazebo/`, procédure et état des essais dans `sitl/README.md`). Les cotes sont dans `sitl/gazebo/terrain.yaml`, seul fichier à modifier ; le monde est généré.
- `sitl/gazebo/vol_demo.py` est testé en SITL. C'est un vol par points connus d'avance, sans vision ni machine à états. Ce n'est pas la mission.
- Le paquet `droneload_mission` n'est pas dans le dépôt. `config/sitl_sans_gps.parm` non plus : la navigation sans GPS n'a pas été simulée depuis ce dépôt.
- Le drone n'a pas volé.

## Règles

- Ne rien présenter comme testé ou validé s'il ne l'a pas été. Distinguer : écrit, testé hors ROS, testé en SITL, testé en vol.
- Ne pas inventer de valeur de paramètre, de référence de composant ou de résultat. Demander.
- Le contrat `/vision/cible` est dans `docs/interface-vision-mission.md`. Le modifier avant le code, jamais après.
- Tout changement de paramètre ArduPilot passe par un fichier `.parm` versionné.
- Le dépôt est public : aucun secret, aucun identifiant Wi-Fi.
- Rédaction en français, phrases courtes, chaque choix technique suivi de sa raison.
- En cas de contradiction entre ce fichier, `architecture/architecture.md` et `docs/interface-vision-mission.md`, ne pas trancher seul : signaler l'écart et demander.

## Architecture complète du drone

@architecture/architecture.md
