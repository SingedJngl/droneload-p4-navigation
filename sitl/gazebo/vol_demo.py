#!/usr/bin/env python3
"""Vol de démonstration sur le terrain Gazebo DroneLoad 2027.

Ce script sert à valider le monde simulé, pas à jouer la mission du concours.
Il suit des points connus d'avance, lus dans terrain.yaml, avec le GPS simulé.
Il n'utilise ni la vision ni la machine à états de droneload_mission.

Il reprend l'enchaînement visé par architecture/architecture.md : décollage en A,
traversée par le passage sûr, dépôt sur une cible, stationnaire de 5 s en zone C,
traversée retour, atterrissage en A. Les critères de largage sont ceux proposés
au paragraphe 3 de l'architecture (section vol de terrain.yaml).

Prérequis : Gazebo, ArduPilot SITL, MAVROS et le pont ros_gz lancés (sitl/README.md).
"""

import argparse
import math
import pathlib
import sys

import rclpy
import yaml
from geometry_msgs.msg import PoseStamped, TwistStamped
from mavros_msgs.msg import State
from mavros_msgs.srv import CommandBool, CommandTOL, SetMode, StreamRate
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy, qos_profile_sensor_data
from std_msgs.msg import Empty

ICI = pathlib.Path(__file__).resolve().parent

# Hauteur du châssis de l'Iris posé au sol dans ardupilot_gazebo. Sert à convertir
# une cote du monde (centre de la fenêtre) en hauteur de vol.
GARDE_AU_SOL = 0.195


class VolDemo(Node):
    def __init__(self, cfg, cible):
        super().__init__("vol_demo")
        self.cfg, self.vol = cfg, cfg["vol"]
        self.altitude = self.vol["hauteur_largage"]
        self.cible = next(c for c in cfg["zone_depot"]["cibles"]["liste"] if c["numero"] == cible)
        depart = cfg["aire_depart"]["aruco"]
        self.depart = (depart["x"], depart["y"])
        self.lacet_depart = math.radians(cfg["drone"]["lacet_deg"])
        self.etat, self.pose, self.vitesse, self.origine, self.sol = None, None, None, None, 0.0

        # /mavros/state demande RELIABLE et TRANSIENT_LOCAL (voir sitl/README.md).
        qos_etat = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE,
                              durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.create_subscription(State, "/mavros/state", self._sur_etat, qos_etat)
        self.create_subscription(PoseStamped, "/mavros/local_position/pose",
                                 self._sur_pose, qos_profile_sensor_data)
        self.create_subscription(TwistStamped, "/mavros/local_position/velocity_local",
                                 self._sur_vitesse, qos_profile_sensor_data)
        self.pub_consigne = self.create_publisher(PoseStamped, "/mavros/setpoint_position/local", 10)
        self.pub_largage = self.create_publisher(Empty, "/largage", 10)
        self.srv_mode = self.create_client(SetMode, "/mavros/set_mode")
        self.srv_armement = self.create_client(CommandBool, "/mavros/cmd/arming")
        self.srv_decollage = self.create_client(CommandTOL, "/mavros/cmd/takeoff")
        self.srv_flux = self.create_client(StreamRate, "/mavros/set_stream_rate")

    def _sur_etat(self, msg):
        self.etat = msg

    def _sur_pose(self, msg):
        self.pose = msg.pose.position

    def _sur_vitesse(self, msg):
        v = msg.twist.linear
        self.vitesse = math.sqrt(v.x ** 2 + v.y ** 2 + v.z ** 2)

    # ---------------------------------------------------------------- outils

    def maintenant(self):
        return self.get_clock().now().nanoseconds / 1e9

    def attendre(self, condition, texte, duree=120.0):
        """Durées en temps mur : sous WSL2 la simulation tourne plus lentement."""
        self.get_logger().info(f"Attente : {texte}")
        fin = self.maintenant() + duree
        while rclpy.ok() and not condition():
            rclpy.spin_once(self, timeout_sec=0.1)
            if self.maintenant() > fin:
                self.get_logger().error(f"Délai dépassé : {texte}")
                sys.exit(1)

    def patienter(self, duree):
        fin = self.maintenant() + duree
        while rclpy.ok() and self.maintenant() < fin:
            rclpy.spin_once(self, timeout_sec=0.1)

    def appeler(self, client, requete):
        client.wait_for_service()
        futur = client.call_async(requete)
        rclpy.spin_until_future_complete(self, futur, timeout_sec=10.0)
        return futur.result()

    def position_terrain(self):
        """Position du drone dans le repère terrain, à partir de la position locale ENU."""
        return (self.pose.x - self.origine[0] + self.depart[0],
                self.pose.y - self.origine[1] + self.depart[1])

    def hauteur(self):
        return self.pose.z - self.sol

    def borner(self, x, y):
        """Consignes bornées aux limites de l'aire de jeu (architecture, paragraphe 3)."""
        t = self.cfg["terrain"]
        return min(max(x, 0.0), t["longueur"]), min(max(y, 0.0), t["largeur"])

    def publier(self, x, y, altitude=None, lacet=None):
        x, y = self.borner(x, y)
        lacet = self.lacet_depart if lacet is None else lacet
        consigne = PoseStamped()
        consigne.header.frame_id = "map"
        consigne.header.stamp = self.get_clock().now().to_msg()
        consigne.pose.position.x = x - self.depart[0] + self.origine[0]
        consigne.pose.position.y = y - self.depart[1] + self.origine[1]
        # Hauteurs comptées depuis le point de décollage, comme le ToF du drone réel.
        # La position locale z, elle, part de l'origine EKF : on ajoute la cote du sol.
        consigne.pose.position.z = self.sol + (self.altitude if altitude is None else altitude)
        consigne.pose.orientation.z = math.sin(lacet / 2)
        consigne.pose.orientation.w = math.cos(lacet / 2)
        self.pub_consigne.publish(consigne)

    def aller(self, x, y, tolerance=0.20, texte=None, altitude=None, lacet=None):
        """Rallie un point du repère terrain. La consigne est republiée en continu."""
        if texte:
            self.get_logger().info(f"{texte} : x={x:.2f} y={y:.2f}")
        cible_z = self.altitude if altitude is None else altitude

        def arrive():
            self.publier(x, y, altitude, lacet)
            px, py = self.position_terrain()
            return math.hypot(px - x, py - y) < tolerance and abs(self.hauteur() - cible_z) < 0.20

        self.attendre(arrive, f"ralliement de ({x:.2f}, {y:.2f})", duree=180.0)

    # --------------------------------------------------------------- séquence

    def decoller(self):
        self.attendre(lambda: self.etat is not None and self.etat.connected, "liaison MAVROS")

        # ArduPilot n'émet la télémétrie que si on la lui demande. MAVProxy le fait
        # de lui-même ; en liaison directe (TCP en SITL, UART sur le drone) il faut le faire ici.
        def demander_flux():
            if self.pose is None or self.vitesse is None:
                self.appeler(self.srv_flux, StreamRate.Request(stream_id=0, message_rate=10, on_off=True))
                self.patienter(2.0)
            return self.pose is not None and self.vitesse is not None
        self.attendre(demander_flux, "position locale (EKF)")

        def passer_guided():
            if self.etat.mode != "GUIDED":
                self.appeler(self.srv_mode, SetMode.Request(custom_mode="GUIDED"))
                self.patienter(1.0)
            return self.etat.mode == "GUIDED"
        self.attendre(passer_guided, "mode GUIDED")

        def armer():
            if not self.etat.armed:
                self.appeler(self.srv_armement, CommandBool.Request(value=True))
                self.patienter(2.0)
            return self.etat.armed
        self.get_logger().info("ARMEMENT")
        self.attendre(armer, "armement (refusé tant que l'EKF n'est pas prêt)", duree=180.0)

        # L'origine du repère terrain est calée sur la position au sol, après armement.
        self.origine = (self.pose.x, self.pose.y)
        self.sol = self.pose.z
        self.get_logger().info(f"DECOLLAGE à {self.altitude:.2f} m")
        reponse = self.appeler(self.srv_decollage, CommandTOL.Request(altitude=self.altitude))
        if reponse is None or not reponse.success:
            self.get_logger().error("Décollage refusé")
            sys.exit(1)
        self.attendre(lambda: self.hauteur() > 0.9 * self.altitude, "altitude de vol")

    def larguer(self):
        """Largue quand l'écart, la vitesse et la hauteur tiennent pendant la durée demandée."""
        v, (x, y) = self.vol, (self.cible["x"], self.cible["y"])
        self.aller(x, y, tolerance=v["ecart_max"], texte=f"CENTRAGE sur la cible {self.cible['numero']}")
        debut = [None]

        def stable():
            self.publier(x, y)
            px, py = self.position_terrain()
            bon = (math.hypot(px - x, py - y) < v["ecart_max"]
                   and self.vitesse < v["vitesse_max"]
                   and abs(self.hauteur() - v["hauteur_largage"]) < v["tolerance_hauteur"])
            if not bon:
                debut[0] = None
            elif debut[0] is None:
                debut[0] = self.maintenant()
            return bon and self.maintenant() - debut[0] >= v["duree_stable"]

        self.attendre(stable, "critères de largage")
        px, py = self.position_terrain()
        self.pub_largage.publish(Empty())
        self.get_logger().info(
            f"LARGAGE : écart {math.hypot(px - x, py - y):.2f} m, "
            f"vitesse {self.vitesse:.2f} m/s, hauteur {self.hauteur():.2f} m")

    def observer_fenetre(self):
        """Stationnaire devant chaque face de la fenêtre, à hauteur de son centre.
        Sert à voir ce que capte la caméra frontale. Le drone ne franchit pas la fenêtre."""
        f = self.cfg["fenetre"]
        recul = 1.5
        self.aller(f["x"] + recul, f["y"], altitude=f["hauteur_centre"] - GARDE_AU_SOL, lacet=math.pi,
                   texte="Fenêtre, face recto")
        self.patienter(6.0)
        self.aller(f["x"] + recul, f["y"], lacet=math.pi)

    def observer_verso(self):
        f = self.cfg["fenetre"]
        recul = 1.5
        # Contournement par le passage sûr, puis face verso, nez vers le poste de pilotage.
        self.aller(f["x"] - recul, f["y"], altitude=f["hauteur_centre"] - GARDE_AU_SOL, lacet=0.0,
                   texte="Fenêtre, face verso")
        self.patienter(6.0)
        self.aller(f["x"] - recul, f["y"], lacet=math.pi)

    def executer(self, fenetre):
        axe = [tuple(p) for p in self.cfg["passage_sur"]["axe"]]
        self.decoller()

        if fenetre:
            self.observer_fenetre()
        for i, (x, y) in enumerate(axe):
            self.aller(x, y, texte=f"TRAVERSEE aller, passage sûr {i + 1}/{len(axe)}")

        self.larguer()

        # En GUIDED, ArduPilot tient la dernière consigne de position : rien à republier.
        self.get_logger().info("Stationnaire de 5 s en zone C")
        self.patienter(5.0)

        for i, (x, y) in enumerate(reversed(axe)):
            self.aller(x, y, texte=f"TRAVERSEE retour, passage sûr {i + 1}/{len(axe)}")
            if fenetre and i == 4:         # point du passage sûr le plus proche de la face verso
                self.observer_verso()
        self.aller(*self.depart, tolerance=0.10, texte="RETOUR à l'aire de départ")
        self.patienter(2.0)

        self.get_logger().info("ATTERRISSAGE")
        self.appeler(self.srv_mode, SetMode.Request(custom_mode="LAND"))
        self.attendre(lambda: not self.etat.armed, "atterrissage et désarmement", duree=180.0)
        px, py = self.position_terrain()
        self.get_logger().info(
            f"TERMINEE : posé à {math.hypot(px - self.depart[0], py - self.depart[1]):.2f} m "
            "du centre de l'ArUco 0")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=pathlib.Path, default=ICI / "terrain.yaml")
    parser.add_argument("--cible", type=int, default=1, help="numéro de la cible annoncée par l'arbitre")
    parser.add_argument("--fenetre", action="store_true",
                        help="ajoute un stationnaire devant chaque face de la fenêtre E")
    args = parser.parse_args()

    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    rclpy.init()
    noeud = VolDemo(cfg, args.cible)
    try:
        noeud.executer(args.fenetre)
    finally:
        noeud.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
