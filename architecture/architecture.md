# Architecture du drone DroneLoad

Complément de `CLAUDE.md` (importé par lui). État au 13/11/2026.

Les règles, la pile logicielle de base et l'état du dépôt sont dans `CLAUDE.md` : ce fichier ne les répète pas.

Statuts employés, conformes aux règles de `CLAUDE.md` :
- **décidé** : choix validé par l'équipe ;
- **proposé** : valeur ou réglage suggéré, jamais appliqué ni testé ;
- **à vérifier** : information non confirmée sur le matériel ou dans le code ;
- **testé hors ROS**, **testé en SITL**, **testé en vol** : niveau de preuve atteint.

## 1. Mission à remplir

Référence : **règlement DroneLoad 2027 V0.1** (08/11/2026), diffusé par Planète Sciences et non versionné dans ce dépôt (décidé le 13/11, en attendant une version suivante). Il prime sur le sujet ECE (décidé le 10/11). Plusieurs annexes de la V0.1 sont encore « à mettre à jour » (images cibles, code du robot).

Vol **intérieur, sans GNSS**. Volière d'environ 10 × 6 m, aire de jeu d'environ 8 × 5 m, motif au sol prévu pour l'optical flow.

Mission unique de 15 min, notée par actions. Une action automatique rapporte plus qu'en manuel. Ligne la plus lourde : **enchaînement automatique décollage → dépôt + traversée → atterrissage en zone A**, 100 points, deux fois. La machine à états doit donc enchaîner dépôt et traversée dans le même vol.

- **Dépôt** : objet ≤ 50 g (disque ferreux Ø40 mm, anneau Ø62 mm) posé sous le drone en zone A. À déposer sur une image A3 parmi 4 cibles et 2 à 4 leurres. Images non publiées.
- **Traversée** : fenêtre E de 100 × 100 cm à hauteur aléatoire, dans les deux sens, ou passage sûr D (suivi de lignes : vert à droite, jaune à gauche). Stationnaire de 5 s au-dessus de la zone C.
- **Robot sol PULL-E** (option) : UART 57600 8N1 en logique 5 V. Commandes ASCII `D` droite, `G` gauche, `A` stop. Réponses `N`, `F`, `S`, puis l'ID de l'image cible. Réponses **à vérifier** : le règlement écrit `'F' (0x56)`, or 0x56 est `V` et `F` vaut 0x46. Ne pas figer ces codes dans l'émulateur avant confirmation de l'organisation.
- **ArUco** : 20 × 20 cm, dictionnaire `DICT_4X4_50`. IDs : 0 zone A, 1 robot, 2-3 alignement, 4-7 fenêtre recto (coins), 8-9 fenêtre verso.
- **Affichage obligatoire** des détections (flux annoté et texte) sur un écran fourni par l'organisation.
- **Seule intervention tolérée en automatique** : valider la fin d'une action. Toute autre consigne (choix de la cible, « plus à droite ») fait compter l'action en manuel.
- **Sécurité imposée** : entraxe ≤ 500 mm, masse ≤ 3 kg, vol ≥ 5 min, reprise manuelle à tout instant, failsafes radio et batterie, coupure moteurs à distance.

Objectifs de l'équipe : largage à 20 cm au plus du centre, 10 min de vol en charge, détection dans 95 % des cas, traitement d'image en moins de 100 ms sur le Pi 5.

## 2. Matériel

```
LiPo 4S 6000 mAh ─XT60─► PM02D (mesure I2C → Pixhawk) ─► distribution ─► 4 ESC ─► 4 moteurs
                    en aval du PM02D : BEC Matek 5,2 V / 5 A ─USB-C─► Pi 5
                                       UBEC 5 V / 3 A ─► rail servo (SERVO9 → MG90S)

Pixhawk 6X  TELEM2 ⇄ Pi 5 (UART, MAVLink 2)     CAN1 ⇄ H-Flow (DroneCAN)
            TELEM1 ⇄ Rx ELRS (CRSF)             SERVO9 ⇄ servo du largueur
Pi 5        CSI ⇄ Camera Module 3 Wide          Wi-Fi 5 GHz ⇄ PC sol (Mission Planner)
```

| Fonction | Composant | Remarques |
|---|---|---|
| Châssis | Holybro X500 V2, entraxe 500 mm | H-Flow sous la Payload Platform Board, Pi 5 au-dessus sur entretoises |
| Propulsion | T-Motor T2814 Pro 1000 KV, hélices 10 × 5 bipales | Protections d'hélice montées en essais et en compétition |
| ESC | T-Motor AIR 20A × 4 | **Risque** : l'eCalc estime environ 36 A par moteur à plein gaz. Courant à mesurer au banc |
| Batterie | LiPo 4S 6000 mAh, 30 C au moins | |
| Contrôleur de vol | Pixhawk 6X et PM02D | Commit firmware fb773567 |
| Compagnon | Raspberry Pi 5, 4 Go | Pas encore monté au 10/11 |
| Caméra | Camera Module 3 Wide (IMX708, 120°) | Montée à l'avant, sur les rails, **pointée vers le sol** (décidé le 13/11) : recherche de la cible, dépôt et atterrissage se font au-dessus du sol. Ne voit pas la fenêtre de la traversée |
| Navigation | Holybro H-Flow | Exige un sol texturé et au moins 5 lux |
| Radio de sécurité | ELRS 2,4 GHz | Indépendante du Pi : une panne du Pi coupe la télémétrie, pas le contrôle |
| Télémétrie | Wi-Fi du Pi 5 en 5 GHz | Le 5 GHz évite de brouiller l'ELRS |
| Largueur | Servo MG90S, mécanisme imprimé | Fonctionne au banc, non monté. Mode de préhension non choisi |

Masse estimée environ 2,1 kg sans protections d'hélice. Poussée/poids et autonomie extrapolés de l'eCalc, **à vérifier** au banc et en vol.

## 3. Logiciel embarqué

| Machine | Rôle |
|---|---|
| Pixhawk 6X | Stabilisation, EKF3, modes STABILIZE, ALT_HOLD, LOITER, GUIDED, LAND, failsafes, Gripper |
| Raspberry Pi 5 | Nœuds `/mission` (P4) et `/vision` (P3), MAVROS, rosbag, relais de télémétrie |
| PC sol | Mission Planner : configuration, calibrations, télémétrie, logs |
| PC de développement | WSL2, SITL, Gazebo Harmonic avec `ardupilot_gazebo`, MAVROS |

### Interface `/vision` → `/mission`

Le contrat fait foi dans `docs/interface-vision-mission.md`. Ne pas le redéfinir ici.

### Machine à états `/mission`

Conception du paquet `droneload_mission` (08/11). **Code hors du dépôt. Testé hors ROS seulement** (simulateur cinématique, faux rclpy). Jamais lancé en SITL. Sert de base de conception, pas de code existant.

Séquence : `ATTENTE → ORIGINE → ARMEMENT → DECOLLAGE → RALLIEMENT → RECHERCHE → CENTRAGE → LARGAGE → RETOUR → ATTERRISSAGE → TERMINEE`. États finaux d'erreur : `REPRISE_MANUELLE`, `PERTE_LIAISON`, `ECHEC`.

Surveillances prévues : liaison avec le contrôleur, désarmement en vol, changement de mode imposé de l'extérieur (on rend la main), batterie, durée maximale.

Seuils **proposés**, à valider en équipe :
- batterie : retour sous 3,6 V par élément, atterrissage sous 3,5 V ;
- largage autorisé si l'écart reste sous 10 cm, la vitesse sous 0,15 m/s et la hauteur à 1,2 m ± 15 cm pendant 1 s ;
- consignes bornées aux limites de l'aire de jeu.

Pour 2027, la séquence doit intégrer la traversée après le dépôt.

### Navigation sans GPS (EKF3)

Réglages **proposés** le 16/10, **à vérifier** sur la Pixhawk :
- capteurs : `FLOW_TYPE=6`, `RNGFND1_TYPE=24`, `RNGFND1_ORIENT=25`, `CAN_P1_DRIVER=1`, `CAN_D1_PROTOCOL=1` ;
- sources : `EK3_SRC1_POSXY=0`, `EK3_SRC1_VELXY=5` (flow), `EK3_SRC1_POSZ=1` (baro), `EK3_SRC1_VELZ=0`, `EK3_SRC1_YAW=1` (compas).

Constat du 27/10 : le baromètre bruite d'environ 30 cm au repos en intérieur. L'altitude fine devra venir du ToF (`EK3_RNG_USE_HGT`, à tester).

L'origine EKF se fixe par `SET_GPS_GLOBAL_ORIGIN` (service MAVROS `set_gp_origin`). Prise en compte réelle **à vérifier** en SITL.

### Comportements ArduPilot à connaître

Relevés dans le code du tag `Copter-4.7.2`, **pas encore observés en SITL** :
- après armement, décoller en moins de 10 s, sinon ArduPilot désarme ;
- en GUIDED, une consigne de vitesse retombe à zéro après `GUID_TIMEOUT` (3 s par défaut) : republier les consignes en continu ;
- `MAV_CMD_DO_GRIPPER` est refusé si `GRIP_ENABLE=0` ; param2 = 0 libère la charge.

Paramètres SITL sans GPS utilisés le 08/11 (**valeurs du paquet hors dépôt**, à recréer dans un `.parm` versionné) : `SIM_GPS1_ENABLE 0`, `GPS1_TYPE 0`, `SIM_FLOW_ENABLE 1`, `FLOW_TYPE 10`, `RNGFND1_TYPE 100`.

### Vision (pôle P3, pour mémoire)

- Écart (m) = écart (px) × hauteur (m) ÷ focale (px), hauteur lue sur le ToF. Corriger d'abord la distorsion du grand angle. La formule suppose une caméra verticale, ce qui est le cas. En vol, le roulis et le tangage décalent le point visé au sol : corriger l'écart avec l'attitude de la Pixhawk (méthode **proposée**, à valider avec P3).
- ArUco par `cv2.aruco`. Méthode de reconnaissance des images A3 non choisie.

## 4. Pièges connus

- `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST` seulement en simulation sur un PC. À retirer pour parler au Pi.
- Faire `deactivate` du venv ArduPilot avant toute commande ROS 2.
- S'abonner à `/mavros/state` en QoS RELIABLE et TRANSIENT_LOCAL.
- Lancer le SITL avec `--out 127.0.0.1:14551` pour MAVROS.
- Sous WSL, `ros2 topic echo` ne voit pas les topics MAVROS, alors qu'un nœud rclpy les reçoit. Tester par script.
- La simulation tourne à environ la moitié du temps réel sous WSL. Aucune latence mesurée en simulation n'est valable.
- OpenCV par apt seulement : `opencv-contrib-python` (pip) casse `cv_bridge`.
- Ne pas compiler MAVROS sur le Pi 5 : 4 Go de RAM ne suffisent pas.
- UART du Pi 5 : `dtparam=uart0=on`, console série désactivée, port `/dev/ttyAMA0`. **À vérifier** sur le Pi monté.
- Robot PULL-E en 5 V, Pi en 3,3 V : adaptateur de niveau obligatoire.

## 5. Échéances qui concernent P4

| Jalon | Date | Contenu |
|---|---|---|
| M2 | 29/11/2026 | Première mission SITL sans GPS : 10 nominales et 6 cas dégradés |
| M3 | 13/12/2026 | Pi 5 à bord, MAVLink fonctionnel |
| M4 | 18/12/2026 | LOITER sans GPS, dérive sous 30 cm sur 60 s |
| M5 (RCE2) | 23/01/2027 | Vol commandé par le Pi, atterrissage sur l'ArUco 0 |
| M7 | 28/03/2027 | Traversée, mission enchaînée en SITL, émulateur du robot |
| M8 (RCE3) | 24/04/2027 | Mission enchaînée en réel, gel du code |
| Finale | 18 au 20/05/2027 | Dates à confirmer |

## 6. Questions ouvertes

- Traversée de la fenêtre : la caméra vers le sol ne voit pas les ArUco 4 à 9. Seconde caméra vers l'avant, ou passage sûr D seulement (suivi de lignes au sol).
- Saisie de la cible annoncée par l'arbitre sans que l'action compte en manuel.
- Liaison avec le robot : UART depuis le drone ou module au sol.
- Comportement de GUIDED sans nouvelle consigne, à observer en SITL.
- Simulation du flow en SITL : fidélité à vérifier.
