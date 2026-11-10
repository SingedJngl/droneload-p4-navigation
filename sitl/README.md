# Simulation SITL

## Lancement

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

Le fichier `config/sitl_sans_gps.parm` arrive avec le paquet `droneload_mission`.

## Pièges connus

- **Gazebo et télémètre.** Avec le backend Gazebo, le télémètre simulé renvoie NaN en Copter 4.7.2. La navigation sans GPS se teste sans Gazebo.
- **Origine EKF.** Sans GPS, l'origine doit être fixée avant tout ordre GUIDED. Le nœud de mission l'envoie par MAVLink.
- **Délai d'armement.** Armer puis décoller en moins de 10 s, sinon ArduPilot désarme.
- **WSL2.** `ros2 topic echo` ne voit pas les topics MAVROS, alors qu'un nœud rclpy les reçoit. Tester par script. L'abonnement à `/mavros/state` demande une QoS RELIABLE et TRANSIENT_LOCAL.
- **Découverte DDS.** `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST` sert à la simulation sur un seul PC. Le retirer pour parler au Pi.
- **Temps simulé.** Sous WSL2 la simulation tourne à environ la moitié du temps réel. Une latence mesurée en simulation ne vaut rien pour le drone.
