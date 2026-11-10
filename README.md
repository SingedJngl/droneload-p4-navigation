# DroneLoad P4 : navigation sans GPS et mission ROS 2

Dépôt du pôle P4 de l'équipe ECE Paris au concours DroneLoad 2027 (Planète Sciences). Il contient le logiciel embarqué sur l'ordinateur compagnon : navigation sans GPS, machine à états de mission, simulation.

Le drone doit décoller, déposer un objet sur une cible, traverser une zone et revenir se poser, sans GPS et sans pilote. Le reste du projet (mécanique, avionique, vision) n'est pas dans ce dépôt.

## Périmètre

| Dans ce dépôt | Hors de ce dépôt |
|---|---|
| Nœud `/mission` (machine à états) | Détection de la cible (P3) |
| Configuration de l'EKF3 sans GPS (optical flow, télémètre) | Réglage des PID, câblage (P2) |
| Simulation SITL de la mission | CAO, largueur (P1) |
| Lancement des nœuds au démarrage du Pi | |
| Contrat d'interface avec la vision | |

## Architecture

```
Pixhawk 6X (ArduPilot Copter 4.7.2)          Raspberry Pi 5 (Ubuntu 24.04, ROS 2 Jazzy)
  stabilisation, EKF3, failsafes    <─ MAVLink 2, UART ─>   MAVROS
  H-Flow (optical flow + ToF, DroneCAN)                      /mission  (machine à états)
                                                             /vision   (P3, autre dépôt)
```

La Pixhawk estime la position à partir de l'optical flow, du télémètre et de l'IMU. Le Pi envoie ses consignes en mode GUIDED par MAVROS. Ce découpage laisse la stabilisation au contrôleur de vol : une panne du Pi ne fait pas tomber le drone.

Séquence nominale : attente, origine EKF, armement, décollage, ralliement, recherche, centrage, largage, retour, atterrissage. Le pilote de sécurité reprend la main à tout instant en changeant de mode sur la radiocommande.

## Choix techniques

- **ROS 2 Jazzy sur Ubuntu 24.04.** La même distribution tourne en simulation et à bord, et elle est maintenue jusqu'en 2029. Humble arrive en fin de vie en mai 2027, le mois de la finale.
- **ArduPilot plutôt que PX4.** L'EKF3 fusionne l'optical flow et le télémètre sans code maison.
- **CycloneDDS** (`RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`) sur toutes les machines, afin d'avoir le même comportement réseau sur le PC et sur le Pi.
- **SITL sans Gazebo pour la navigation sans GPS.** Avec Gazebo, le télémètre simulé d'ArduPilot 4.7.2 renvoie NaN. Le modèle multicoptère interne de SITL simule le flow et le télémètre.

## Arborescence

```
src/        paquets ROS 2 (espace de travail colcon)
config/     paramètres ArduPilot : SITL et drone réel
sitl/       procédure et scripts de lancement de la simulation
scripts/    outils d'analyse des essais
docs/       contrat d'interface, notes de conception
logs/       résultats d'essais légers (résumés, figures), jamais les rosbags
```

## Démarrage

Prérequis : Ubuntu 24.04 (natif ou WSL2), ROS 2 Jazzy, MAVROS installé par apt, ArduPilot SITL au tag `Copter-4.7.2`.

```bash
git clone https://github.com/SingedJngl/droneload-p4-navigation.git
cd droneload-p4-navigation
colcon build --symlink-install
source install/setup.bash
```

La procédure de simulation est dans [`sitl/README.md`](sitl/README.md).

## État

| Élément | État au 11/11/2026 |
|---|---|
| Décollage GUIDED commandé par MAVROS en SITL | fait le 30/10 |
| Paquet `droneload_mission` (machine à états, campagne de 10 missions nominales et 6 cas dégradés) | écrit, testé hors ROS, à ajouter au dépôt |
| Mission complète en SITL sans GPS | à faire, objectif 29/11 |
| Pi 5 à bord, liaison MAVLink | à faire, objectif 13/12 |
| Stationnaire sans GPS, dérive sous 30 cm en 60 s | à faire, objectif 18/12 |

Le drone n'a pas encore volé. Aucun résultat de ce dépôt n'est validé en vol réel.

## Règles de contribution

Voir [`CONTRIBUTING.md`](CONTRIBUTING.md).
