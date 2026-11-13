# Simulation SITL

Deux simulations, deux usages.

| Simulation | Sert à | Positionnement |
|---|---|---|
| SITL sans Gazebo | Navigation sans GPS (EKF3, flow, télémètre) | Flow et télémètre simulés par SITL |
| SITL avec Gazebo | Terrain du concours, caméra, logique de mission | GPS simulé |

Gazebo ne remplace pas la simulation sans GPS : avec lui, le télémètre simulé renvoie NaN en Copter 4.7.2. Le monde Gazebo vole donc au GPS simulé. Il valide la géométrie de la mission et ce que voit la caméra, pas l'estimation de position.

## SITL sans Gazebo

Trois terminaux. Désactiver le venv ArduPilot (`deactivate`) avant toute commande ROS 2, sinon les paquets Python entrent en conflit.

```bash
# 1. ArduPilot SITL, sans GPS, sans Gazebo
sim_vehicle.py -v ArduCopter -f X -w \
  --add-param-file=config/sitl_sans_gps.parm \
  --out 127.0.0.1:14551

# 2. MAVROS
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
ros2 launch mavros apm.launch fcu_url:=udp://:14551@

# 3. Mission
source install/setup.bash
# commande de lancement à compléter avec le paquet droneload_mission
```

Le fichier `config/sitl_sans_gps.parm` n'est pas encore dans le dépôt.

## SITL avec Gazebo : terrain DroneLoad 2027

Le monde reproduit le terrain du règlement V0.1 (`docs/V0.1_Règlement_Droneload_2027.pdf`) : Terrain de jeux, aire de départ A, zone B avec fenêtre E, obstacles F et passage sûr D, zone C avec les quatre cibles, robot PULL-E sur son rail et ArUco 0 à 9.

### Fichiers

| Fichier | Rôle |
|---|---|
| `gazebo/terrain.yaml` | Cotes du terrain. Seul fichier à modifier. |
| `gazebo/generer_monde.py` | Génère le monde et les textures dans `gazebo/genere/` (non versionné). |
| `lancer_gazebo.sh` | Génère le monde puis lance Gazebo. |
| `gazebo/vol_demo.py` | Vol de validation du monde, par points connus d'avance. |

Le monde est généré parce que le règlement annonce des dimensions susceptibles de changer et une fenêtre à hauteur aléatoire. `terrain.yaml` marque l'origine de chaque valeur : `[R]` règlement, `[F]` lue sur la figure 1, `[H]` hypothèse.

### Prérequis

Gazebo Harmonic, le plugin `ardupilot_gazebo` compilé dans `~/ardupilot_gazebo` (sinon, variable `ARDUPILOT_GAZEBO`), `ros-jazzy-ros-gz`, `python3-opencv`, `python3-yaml`.

### Lancement

Cinq terminaux.

```bash
# 1. Gazebo. Options : --sans-ihm, --hauteur-fenetre 1.2
sitl/lancer_gazebo.sh

# 2. ArduPilot SITL relié à Gazebo
sim_vehicle.py -v ArduCopter -f gazebo-iris --model JSON --out 127.0.0.1:14551

# 3. MAVROS
ros2 launch mavros apm.launch fcu_url:=udp://:14551@

# 4. Pont ROS 2 / Gazebo : caméras, largage, robot
ros2 run ros_gz_bridge parameter_bridge   "/camera/image@sensor_msgs/msg/Image[gz.msgs.Image"   "/camera_avant/image@sensor_msgs/msg/Image[gz.msgs.Image"   "/largage@std_msgs/msg/Empty]gz.msgs.Empty"   "/pull_e/cmd_vel@std_msgs/msg/Float64]gz.msgs.Double"

# 5. Vol de validation. --fenetre ajoute un stationnaire devant chaque face de la fenêtre E
python3 sitl/gazebo/vol_demo.py --cible 2 --fenetre
```

Le terminal 2 se lance dans le venv ArduPilot, les terminaux 3 à 5 hors du venv. Au premier lancement, `sim_vehicle.py` peut recompiler ArduPilot pendant plusieurs minutes : attendre la ligne `SIM_VEHICLE: Run MavProxy` avant de lancer MAVROS.

### Repère

Origine au coin du Terrain de jeux côté zone C. x le long des 8 m vers le poste de pilotage, y le long des 5 m, z vers le haut. Ce repère est celui du monde Gazebo. La position locale ENU de MAVROS (`/mavros/local_position/pose`) s'y exprime directement : au sol sur l'ArUco 0, elle vaut (7,5 ; 3,7).

### Interfaces simulées

| Topic ROS 2 | Type | Effet |
|---|---|---|
| `/camera/image` | `sensor_msgs/Image` | Caméra ventrale, haut de l'image vers l'avant du drone |
| `/camera_avant/image` | `sensor_msgs/Image` | Caméra frontale, optionnelle |
| `/largage` | `std_msgs/Empty` | Détache l'objet porté sous le drone |
| `/pull_e/cmd_vel` | `std_msgs/Float64` | Vitesse du robot sur son rail, en m/s |

La caméra ventrale reprend le Camera Module 3 Wide de l'architecture : pointée vers le sol, champ horizontal de 102° (120° en diagonale). Sa résolution (1536 × 864) et sa position exacte sont des hypothèses.

La caméra frontale n'existe pas sur le drone. Elle sert à instruire la question ouverte de l'architecture sur la traversée de la fenêtre. Elle se désactive dans `terrain.yaml` (`drone.camera_avant.active`).

Les deux caméras sont des sténopés parfaits : pas de distorsion de grand angle, pas de flou, éclairage uniforme. Une détection réussie en simulation ne garantit rien sur le drone.

### Vol de validation

`vol_demo.py` suit des points connus d'avance au GPS simulé. Il n'utilise ni la vision ni `droneload_mission`. Il enchaîne décollage, traversée par le passage sûr, dépôt, stationnaire de 5 s, traversée retour et atterrissage en A.

Il applique les seuils proposés dans l'architecture, repris dans la section `vol` de `terrain.yaml` : vol à 1,20 m, largage quand l'écart reste sous 10 cm, la vitesse sous 0,15 m/s et la hauteur à ± 15 cm pendant 1 s. Les consignes sont bornées au Terrain de jeux. Les hauteurs sont comptées depuis le point de décollage.

### Ce qui n'est pas simulé

- Les images des cibles (annexe 3) et les leurres : non publiés. Les cibles sont des affiches A3 de couleur portant un chiffre.
- Le protocole UART du robot (`D`, `G`, `A`, réponses `N`, `F`, `S`) : le robot simulé ne reçoit qu'une vitesse.
- Le largueur à servo et `MAV_CMD_DO_GRIPPER` : le largage passe par un topic Gazebo, pas par ArduPilot.
- La volière : seule son emprise au sol est représentée, sa hauteur n'est pas dans le règlement.
- Le drone : modèle Iris d'`ardupilot_gazebo`, pas le X500 V2. Masse, inertie et poussée ne sont pas celles du drone.
- La navigation sans GPS : le monde Gazebo vole au GPS simulé.

### État des essais

Testé en SITL avec Gazebo le 13/11/2026, sous WSL2, par la procédure ci-dessus (`sim_vehicle.py`, MAVProxy, MAVROS en UDP). Un vol `vol_demo.py --cible 2 --fenetre` :

- La séquence va au bout, de l'armement au désarmement.
- Largage déclenché à 4 cm d'écart, 0,06 m/s et 1,19 m. L'objet repose à 12 cm du centre de la cible 2, sur l'affiche. Seule la position finale est mesurée, pas le premier contact.
- Le drone se pose à 2 cm du centre de l'ArUco 0.
- Caméra ventrale : ArUco 0, 1, 2 et 3 détectés par OpenCV. Elle ne détecte aucun des ArUco 4 à 9 de la fenêtre.
- Caméra frontale : ArUco 4 à 7 détectés devant la face recto, 8 et 9 devant la face verso, à 1,5 m de la fenêtre.
- Caméra frontale : deux fausses détections sur deux vols (ids 17 et 37, absents du terrain). La vision devra filtrer les ids attendus.

Testé sur un vol précédent : le robot atteint sa butée sur une consigne de vitesse.

Non testé : le passage à travers la fenêtre, la détection par les nœuds de P3, la machine à états `droneload_mission` (pas encore dans le dépôt). Rien de tout cela n'a été testé en vol.

## Pièges connus

- **Gazebo et télémètre.** Avec le backend Gazebo, le télémètre simulé renvoie NaN en Copter 4.7.2. La navigation sans GPS se teste sans Gazebo.
- **Origine EKF.** Sans GPS, l'origine doit être fixée avant tout ordre GUIDED. Le nœud de mission l'envoie par MAVLink.
- **Délai d'armement.** Armer puis décoller en moins de 10 s, sinon ArduPilot désarme.
- **Flux de télémétrie.** Sans MAVProxy sur la liaison, ArduPilot n'émet pas la position. Il faut appeler `/mavros/set_stream_rate`, comme le fait `vol_demo.py`. Le cas se présentera sur l'UART du drone.
- **Hauteur locale.** La position locale z part de l'origine EKF, pas du point de décollage. Une consigne de hauteur s'écrit : cote au sol relevée avant le décollage, plus la hauteur voulue.
- **Chemins Gazebo.** `~/.bashrc` n'est pas lu hors shell interactif. `lancer_gazebo.sh` fixe lui-même `GZ_SIM_SYSTEM_PLUGIN_PATH` et `GZ_SIM_RESOURCE_PATH`.
- **WSL2.** `ros2 topic echo` ne voit pas les topics MAVROS, alors qu'un nœud rclpy les reçoit. Tester par script. L'abonnement à `/mavros/state` demande une QoS RELIABLE et TRANSIENT_LOCAL.
- **Découverte DDS.** `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST` sert à la simulation sur un seul PC. Le retirer pour parler au Pi.
- **Temps simulé.** Sous WSL2 la simulation tourne à environ la moitié du temps réel. Une latence mesurée en simulation ne vaut rien pour le drone.
