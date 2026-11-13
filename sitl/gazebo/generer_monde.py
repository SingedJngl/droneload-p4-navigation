#!/usr/bin/env python3
"""Génère le monde Gazebo du terrain DroneLoad 2027 à partir de terrain.yaml.

Le monde est généré et non écrit à la main : le règlement annonce que les
dimensions peuvent changer, et la hauteur de la fenêtre est tirée au hasard.
Une seule source, terrain.yaml, évite un monde et une documentation qui divergent.

Sortie : <sortie>/droneload_2027.sdf et <sortie>/textures/*.png.
Dépendances : python3-yaml, numpy, OpenCV avec le module aruco.
"""

import argparse
import math
import pathlib
import sys

import cv2
import numpy as np
import yaml

ICI = pathlib.Path(__file__).resolve().parent

ROUGE = (0.85, 0.10, 0.10)
BLANC = (0.95, 0.95, 0.95)
BLEU = (0.10, 0.35, 0.80)
VERT = (0.20, 0.65, 0.15)
JAUNE = (0.95, 0.80, 0.10)
GRIS = (0.45, 0.45, 0.50)
MAGENTA = (0.75, 0.15, 0.45)


# --------------------------------------------------------------------------
# Textures
# --------------------------------------------------------------------------

def texture_aruco(dossier, dictionnaire, ident):
    """Marqueur avec une marge blanche d'une case, nécessaire à la détection."""
    dico = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, dictionnaire))
    cases = dico.markerSize + 2            # bordure noire comprise
    px = 40
    # OpenCV 4.6 (paquet apt d'Ubuntu 24.04) nomme la fonction drawMarker,
    # les versions 4.7 et suivantes generateImageMarker.
    dessiner = getattr(cv2.aruco, "generateImageMarker", None) or cv2.aruco.drawMarker
    marqueur = dessiner(dico, ident, cases * px)
    image = cv2.copyMakeBorder(marqueur, px, px, px, px,
                               cv2.BORDER_CONSTANT, value=255)
    chemin = dossier / f"aruco_{ident}.png"
    cv2.imwrite(str(chemin), image)
    return chemin, (cases + 2) / cases     # rapport plaque / marqueur


def texture_cible(dossier, numero, couleur, format_m):
    largeur = 600
    hauteur = round(largeur * format_m[1] / format_m[0])
    bgr = tuple(int(255 * c) for c in reversed(couleur))
    image = np.full((hauteur, largeur, 3), bgr, np.uint8)
    texte = str(numero)
    police, echelle, trait = cv2.FONT_HERSHEY_SIMPLEX, 14, 40
    (tl, th), _ = cv2.getTextSize(texte, police, echelle, trait)
    cv2.putText(image, texte, ((largeur - tl) // 2, (hauteur + th) // 2),
                police, echelle, (255, 255, 255), trait, cv2.LINE_AA)
    chemin = dossier / f"cible_{numero}.png"
    cv2.imwrite(str(chemin), image)
    return chemin


def texture_sol(dossier):
    """Bâche sombre à motif : le règlement annonce un motif pour le flux optique."""
    rng = np.random.default_rng(2027)      # graine fixe : monde reproductible
    grossier = rng.integers(25, 70, (120, 200), dtype=np.uint8)
    image = cv2.resize(grossier, (2000, 1200), interpolation=cv2.INTER_NEAREST)
    chemin = dossier / "sol.png"
    cv2.imwrite(str(chemin), cv2.cvtColor(image, cv2.COLOR_GRAY2BGR))
    return chemin


# --------------------------------------------------------------------------
# Briques SDF
# --------------------------------------------------------------------------

def materiau(couleur, alpha=1.0):
    r, g, b = couleur
    return (f"<material><ambient>{r} {g} {b} {alpha}</ambient>"
            f"<diffuse>{r} {g} {b} {alpha}</diffuse>"
            f"<specular>0.05 0.05 0.05 1</specular></material>")


def materiau_texture(chemin):
    return ("<material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse>"
            "<specular>0 0 0 1</specular>"
            f"<pbr><metal><albedo_map>{chemin}</albedo_map>"
            "<metalness>0</metalness><roughness>1</roughness></metal></pbr></material>")


def visuel_boite(nom, pose, taille, couleur, alpha=1.0):
    return (f'<visual name="{nom}"><pose>{pose}</pose><cast_shadows>0</cast_shadows>'
            f"<geometry><box><size>{taille[0]:.4f} {taille[1]:.4f} {taille[2]:.4f}</size></box></geometry>"
            f"{materiau(couleur, alpha)}</visual>")


def collision_boite(nom, pose, taille):
    return (f'<collision name="{nom}"><pose>{pose}</pose>'
            f"<geometry><box><size>{taille[0]:.4f} {taille[1]:.4f} {taille[2]:.4f}</size></box></geometry>"
            "</collision>")


def visuel_plan(nom, pose, taille, texture):
    return (f'<visual name="{nom}"><pose>{pose}</pose><cast_shadows>0</cast_shadows>'
            f"<geometry><plane><normal>0 0 1</normal><size>{taille[0]:.4f} {taille[1]:.4f}</size></plane></geometry>"
            f"{materiau_texture(texture)}</visual>")


class Marquage:
    """Bandes posées au sol, sans collision. Chaque couche a sa cote z pour
    éviter le scintillement entre surfaces confondues."""

    def __init__(self):
        self.visuels = []

    def bande(self, x1, y1, x2, y2, largeur, couleur, z=0.002):
        longueur = math.hypot(x2 - x1, y2 - y1)
        lacet = math.atan2(y2 - y1, x2 - x1)
        pose = f"{(x1 + x2) / 2:.4f} {(y1 + y2) / 2:.4f} {z} 0 0 {lacet:.5f}"
        nom = f"bande_{len(self.visuels)}"
        self.visuels.append(visuel_boite(nom, pose, (longueur, largeur, 0.001), couleur))

    def ligne(self, points, largeur, couleur, z=0.002):
        for (x1, y1), (x2, y2) in zip(points, points[1:]):
            self.bande(x1, y1, x2, y2, largeur, couleur, z)

    def plaque(self, nom, x, y, taille, texture, lacet=0.0, z=0.004):
        self.visuels.append(visuel_plan(nom, f"{x} {y} {z} 0 0 {lacet}", taille, texture))

    def sdf(self):
        return ('<model name="marquage"><static>1</static><link name="link">'
                + "".join(self.visuels) + "</link></model>")


# --------------------------------------------------------------------------
# Géométrie du passage sûr
# --------------------------------------------------------------------------

def lisser(points, passes=3):
    """Lissage de Chaikin. Les extrémités sont conservées."""
    pts = [tuple(p) for p in points]
    for _ in range(passes):
        nouveau = [pts[0]]
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            nouveau.append((0.75 * x1 + 0.25 * x2, 0.75 * y1 + 0.25 * y2))
            nouveau.append((0.25 * x1 + 0.75 * x2, 0.25 * y1 + 0.75 * y2))
        nouveau.append(pts[-1])
        pts = nouveau
    return pts


def decaler(points, distance):
    """Décale la ligne vers la droite du sens de parcours (distance > 0)."""
    sortie = []
    for i, (x, y) in enumerate(points):
        xa, ya = points[max(i - 1, 0)]
        xb, yb = points[min(i + 1, len(points) - 1)]
        dx, dy = xb - xa, yb - ya
        n = math.hypot(dx, dy)
        sortie.append((x + distance * dy / n, y - distance * dx / n))
    return sortie


def distance_point_ligne(p, points):
    px, py = p
    mini = float("inf")
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        dx, dy = x2 - x1, y2 - y1
        t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        mini = min(mini, math.hypot(px - x1 - t * dx, py - y1 - t * dy))
    return mini


# --------------------------------------------------------------------------
# Éléments du terrain
# --------------------------------------------------------------------------

def plaque_aruco_verticale(nom, x, y, z, vers_x_positif, cote_plaque, texture):
    """Plaque verticale dont la face imprimée regarde vers +x ou vers -x."""
    lacet = math.pi / 2 if vers_x_positif else -math.pi / 2
    return visuel_plan(nom, f"{x:.4f} {y:.4f} {z:.4f} {math.pi / 2:.5f} 0 {lacet:.5f}",
                       (cote_plaque, cote_plaque), texture)


def modele_fenetre(cfg, hauteur_centre, plaque, textures):
    f = cfg["fenetre"]
    s, o = f["section_cadre"], f["ouverture"]
    demi = o / 2 + s / 2
    haut = hauteur_centre + o / 2 + s
    elements = []
    barres = {
        "montant_gauche": (f"0 {-demi} {haut / 2} 0 0 0", (s, s, haut)),
        "montant_droit": (f"0 {demi} {haut / 2} 0 0 0", (s, s, haut)),
        "traverse_haute": (f"0 0 {hauteur_centre + demi} 0 0 0", (s, o + 2 * s, s)),
        "traverse_basse": (f"0 0 {hauteur_centre - demi} 0 0 0", (s, o + 2 * s, s)),
    }
    for nom, (pose, taille) in barres.items():
        elements.append(visuel_boite(nom, pose, taille, MAGENTA))
        elements.append(collision_boite(nom, pose, taille))

    # Le règlement place les ArUco aux coins, hors des diagonales (recto), et
    # alignés verticalement hors du centre (verso). Décalages lus sur les
    # figures de la page 12 : plaque au-dessus ou au-dessous de l'ouverture,
    # son bord latéral aligné sur le bord de l'ouverture.
    dy = o / 2 - plaque / 2
    dz = o / 2 + plaque / 2
    face = s / 2 + 0.003
    # Vu du poste de pilotage (regard vers -x), la droite est vers +y.
    recto = {4: (dy, -dz), 5: (dy, dz), 6: (-dy, dz), 7: (-dy, -dz)}
    # Vu de la zone C (regard vers +x), la gauche est vers +y.
    verso = {8: (dy, -dz), 9: (dy, dz)}
    for ident, (y, z) in recto.items():
        fond = f"{face - 0.002} {y} {hauteur_centre + z} 0 0 0"
        elements.append(visuel_boite(f"fond_{ident}", fond, (0.002, plaque, plaque), BLANC))
        elements.append(plaque_aruco_verticale(f"aruco_{ident}", face, y, hauteur_centre + z,
                                               True, plaque, textures[ident]))
    for ident, (y, z) in verso.items():
        fond = f"{-face + 0.002} {y} {hauteur_centre + z} 0 0 0"
        elements.append(visuel_boite(f"fond_{ident}", fond, (0.002, plaque, plaque), BLANC))
        elements.append(plaque_aruco_verticale(f"aruco_{ident}", -face, y, hauteur_centre + z,
                                               False, plaque, textures[ident]))
    return (f'<model name="fenetre"><static>1</static><pose>{f["x"]} {f["y"]} 0 0 0 0</pose>'
            '<link name="link">' + "".join(elements) + "</link></model>")


def modele_obstacle(nom, x, y, cote, hauteur):
    r = cote / math.sqrt(3)                # rayon du cercle circonscrit
    sommets = "".join(
        f"<point>{r * math.cos(a):.4f} {r * math.sin(a):.4f}</point>"
        for a in (math.pi / 2, math.pi / 2 + 2 * math.pi / 3, math.pi / 2 + 4 * math.pi / 3))
    geometrie = f"<geometry><polyline>{sommets}<height>{hauteur}</height></polyline></geometry>"
    # Collision en cylindre circonscrit : plus simple pour le moteur physique,
    # et majorante pour un essai d'évitement.
    collision = (f'<collision name="collision"><pose>0 0 {hauteur / 2} 0 0 0</pose>'
                 f"<geometry><cylinder><radius>{r:.4f}</radius><length>{hauteur}</length></cylinder></geometry>"
                 "</collision>")
    return (f'<model name="{nom}"><static>1</static><pose>{x} {y} 0 0 0 0</pose><link name="link">'
            f'<visual name="visuel">{geometrie}{materiau((0.95, 0.75, 0.80))}</visual>'
            f"{collision}</link></model>")


def modele_blocage(b):
    longueur = b["y_max"] - b["y_min"]
    pose = f"0 0 {b['hauteur'] / 2} 0 0 0"
    taille = (0.02, longueur, b["hauteur"])
    return (f'<model name="blocage_visuel"><static>1</static>'
            f'<pose>{b["x"]} {(b["y_min"] + b["y_max"]) / 2} 0 0 0 0</pose><link name="link">'
            + visuel_boite("visuel", pose, taille, GRIS) + collision_boite("collision", pose, taille)
            + "</link></model>")


def modele_robot(r, plaque, texture):
    lx, ly, lz = r["taille"]
    garde = 0.02                           # le châssis ne frotte pas le sol
    pose = f"0 0 {garde + (lz - garde) / 2} 0 0 0"
    taille = (lx, ly, lz - garde)
    return f"""
    <model name="pull_e">
      <pose>{r["x"]} {r["y_depart"]} 0 0 0 0</pose>
      <link name="chassis">
        <inertial><mass>2.0</mass>
          <inertia><ixx>0.02</ixx><iyy>0.02</iyy><izz>0.03</izz><ixy>0</ixy><ixz>0</ixz><iyz>0</iyz></inertia>
        </inertial>
        {visuel_boite("visuel", pose, taille, BLANC)}
        {collision_boite("collision", pose, taille)}
        {visuel_plan("aruco", f"0 0 {lz + 0.002} 0 0 0", (plaque, plaque), texture)}
      </link>
      <joint name="rail" type="prismatic">
        <parent>world</parent>
        <child>chassis</child>
        <axis><xyz>0 1 0</xyz>
          <!-- Sans limite d'effort, la commande en vitesse ignore les butées. -->
          <limit><lower>{r["y_min"] - r["y_depart"]:.3f}</lower><upper>{r["y_max"] - r["y_depart"]:.3f}</upper>
            <effort>1e6</effort></limit>
        </axis>
      </joint>
      <!-- Consigne de vitesse le long du rail, en m/s (gz.msgs.Double). -->
      <plugin filename="gz-sim-joint-controller-system" name="gz::sim::systems::JointController">
        <joint_name>rail</joint_name>
        <topic>/pull_e/cmd_vel</topic>
        <initial_velocity>0</initial_velocity>
      </plugin>
    </model>"""


def capteur_camera(nom, pose, cam):
    return f"""
        <sensor name="{nom}" type="camera">
          <pose>{pose}</pose>
          <topic>{cam["topic"]}</topic>
          <update_rate>{cam["cadence_hz"]}</update_rate>
          <always_on>1</always_on>
          <camera>
            <horizontal_fov>{math.radians(cam["champ_horizontal_deg"]):.4f}</horizontal_fov>
            <image><width>{cam["largeur_px"]}</width><height>{cam["hauteur_px"]}</height></image>
            <clip><near>0.02</near><far>50</far></clip>
          </camera>
        </sensor>"""


def modeles_drone(cfg):
    a = cfg["aire_depart"]["aruco"]
    d, o, cam = cfg["drone"], cfg["objet"], cfg["drone"]["camera"]
    z_base = 0.195                         # hauteur de base_link au sol, valeur d'ardupilot_gazebo
    z_objet = -0.11
    px, py, pz = cam["position"]
    # L'axe optique est l'axe x du capteur : tangage de 90 degrés pour viser le sol.
    # Le haut de l'image pointe alors vers l'avant du drone.
    capteurs = capteur_camera("camera", "0 0 0 0 1.5708 0", cam)
    avant = d.get("camera_avant", {})
    if avant.get("active"):
        ax, ay, az = avant["position"]
        capteurs += capteur_camera("camera_avant", f"{ax - px} {ay - py} {az - pz} 0 0 0", avant)
    rayon = o["diametre"] / 2
    ixx = o["masse"] * (3 * rayon ** 2 + o["epaisseur"] ** 2) / 12
    izz = o["masse"] * rayon ** 2 / 2
    return f"""
    <model name="drone">
      <pose degrees="true">{a["x"]} {a["y"]} {z_base} 0 0 {d["lacet_deg"]}</pose>
      <include><uri>model://iris_with_ardupilot</uri></include>

      <!-- Support : porte les caméras et retient l'objet à déposer. -->
      <link name="support">
        <pose>{px} {py} {pz} 0 0 0</pose>
        <inertial><mass>0.02</mass>
          <inertia><ixx>1e-5</ixx><iyy>1e-5</iyy><izz>1e-5</izz><ixy>0</ixy><ixz>0</ixz><iyz>0</iyz></inertia>
        </inertial>
        {visuel_boite("visuel", "0 0 0.01 0 0 0", (0.03, 0.03, 0.02), GRIS)}
        {capteurs}
      </link>
      <joint name="support_fixe" type="fixed">
        <parent>iris_with_ardupilot::iris_with_standoffs::base_link</parent>
        <child>support</child>
      </joint>

      <!-- Largage : publier un gz.msgs.Empty sur /largage détache l'objet. -->
      <plugin filename="gz-sim-detachable-joint-system" name="gz::sim::systems::DetachableJoint">
        <parent_link>support</parent_link>
        <child_model>objet</child_model>
        <child_link>corps</child_link>
        <detach_topic>/largage</detach_topic>
      </plugin>
    </model>

    <model name="objet">
      <pose>{a["x"]} {a["y"]} {z_base + z_objet} 0 0 0</pose>
      <link name="corps">
        <inertial><mass>{o["masse"]}</mass>
          <inertia><ixx>{ixx:.3e}</ixx><iyy>{ixx:.3e}</iyy><izz>{izz:.3e}</izz><ixy>0</ixy><ixz>0</ixz><iyz>0</iyz></inertia>
        </inertial>
        <visual name="visuel">
          <geometry><cylinder><radius>{rayon}</radius><length>{o["epaisseur"]}</length></cylinder></geometry>
          {materiau((0.95, 0.45, 0.05))}
        </visual>
        <collision name="collision">
          <geometry><cylinder><radius>{rayon}</radius><length>{o["epaisseur"]}</length></cylinder></geometry>
        </collision>
      </link>
    </model>"""


# --------------------------------------------------------------------------
# Assemblage
# --------------------------------------------------------------------------

def verifier_degagement(cfg, axe):
    """Le règlement interdit tout obstacle à moins de 50 cm du passage sûr."""
    p, obs, f = cfg["passage_sur"], cfg["obstacles"], cfg["fenetre"]
    demi_passage = p["entraxe_lignes"] / 2 + cfg["terrain"]["largeur_ruban"] / 2
    rayon = obs["cote"] / math.sqrt(3)
    solides = [(f"obstacle {i + 1}", (o["x"], o["y"]), rayon) for i, o in enumerate(obs["liste"])]
    demi_cadre = f["ouverture"] / 2 + f["section_cadre"]
    for signe in (-1, 1):
        solides.append(("montant de fenêtre", (f["x"], f["y"] + signe * demi_cadre), f["section_cadre"]))
    erreurs = []
    for nom, centre, r in solides:
        libre = distance_point_ligne(centre, axe) - r - demi_passage
        if libre < p["degagement"]:
            erreurs.append(f"{nom} à {libre:.2f} m du passage sûr (minimum {p['degagement']} m)")
    return erreurs


def generer(cfg, sortie, hauteur_fenetre):
    textures_dir = sortie / "textures"
    textures_dir.mkdir(parents=True, exist_ok=True)

    aruco = cfg["aruco"]
    textures, rapport = {}, 1.0
    for ident in range(10):                # ids 0 à 9 de l'annexe 4
        textures[ident], rapport = texture_aruco(textures_dir, aruco["dictionnaire"], ident)
    plaque = aruco["cote"] * rapport       # marqueur de 20 cm plus sa marge blanche

    t, v = cfg["terrain"], cfg["voliere"]
    L, l, w = t["longueur"], t["largeur"], t["largeur_ruban"]
    m = Marquage()

    # Contour du Terrain de jeux : rouge à l'intérieur, blanc à l'extérieur.
    for d, couleur in ((w / 2, ROUGE), (-w / 2, BLANC)):
        coins = [(d, d), (L - d, d), (L - d, l - d), (d, l - d), (d, d)]
        m.ligne(coins, w, couleur)

    # Aire de départ : marquage bleu, ArUco 0.
    a = cfg["aire_depart"]
    m.ligne([(a["x_min"], l - w), (a["x_min"], a["y_min"]), (L - w, a["y_min"])], w, BLEU)
    m.plaque("aruco_0", a["aruco"]["x"], a["aruco"]["y"], (plaque, plaque), textures[0])

    # Limite entre C et B : bleu côté C, blanc côté B.
    c = cfg["zone_depot"]
    m.bande(c["x_max"] - w / 2, w, c["x_max"] - w / 2, l - w, w, BLEU)
    m.bande(c["x_max"] + w / 2, w, c["x_max"] + w / 2, l - w, w, BLANC)

    # Cibles de dépôt.
    fmt = c["cibles"]["format"]
    for cible in c["cibles"]["liste"]:
        tex = texture_cible(textures_dir, cible["numero"], cible["couleur"], fmt)
        m.plaque(f"cible_{cible['numero']}", cible["x"], cible["y"], fmt, tex)

    # Zone robot : rail et ArUco d'alignement.
    r = cfg["robot"]
    m.bande(r["x"], r["y_min"], r["x"], r["y_max"], 0.03, GRIS)
    for al in r["arucos_alignement"]:
        m.plaque(f"aruco_{al['id']}", al["x"], al["y"], (plaque, plaque), textures[al["id"]])

    # Passage sûr. Sens de parcours A vers C : le vert est à droite.
    p = cfg["passage_sur"]
    axe = lisser(p["axe"])
    m.ligne(decaler(axe, p["entraxe_lignes"] / 2), w, VERT, z=0.003)
    m.ligne(decaler(axe, -p["entraxe_lignes"] / 2), w, JAUNE, z=0.003)

    erreurs = verifier_degagement(cfg, axe)
    if erreurs:
        sys.exit("terrain.yaml incohérent avec le règlement :\n  " + "\n  ".join(erreurs))

    obs = cfg["obstacles"]
    obstacles = "".join(modele_obstacle(f"obstacle_{i + 1}", o["x"], o["y"], obs["cote"], obs["hauteur"])
                        for i, o in enumerate(obs["liste"]))

    sol = texture_sol(textures_dir)
    monde = f"""<?xml version="1.0" ?>
<!-- Fichier généré par sitl/gazebo/generer_monde.py. Ne pas modifier : éditer terrain.yaml. -->
<sdf version="1.9">
  <world name="droneload_2027">
    <physics name="1ms" type="ignore">
      <max_step_size>0.001</max_step_size>
      <real_time_factor>1.0</real_time_factor>
    </physics>
    <plugin filename="gz-sim-physics-system" name="gz::sim::systems::Physics"/>
    <plugin filename="gz-sim-sensors-system" name="gz::sim::systems::Sensors">
      <render_engine>ogre2</render_engine>
    </plugin>
    <plugin filename="gz-sim-user-commands-system" name="gz::sim::systems::UserCommands"/>
    <plugin filename="gz-sim-scene-broadcaster-system" name="gz::sim::systems::SceneBroadcaster"/>
    <plugin filename="gz-sim-imu-system" name="gz::sim::systems::Imu"/>
    <plugin filename="gz-sim-navsat-system" name="gz::sim::systems::NavSat"/>

    <scene>
      <ambient>1.0 1.0 1.0</ambient>
      <background>0.8 0.8 0.8</background>
    </scene>

    <!-- Coordonnées du monde ardupilot_gazebo d'origine, cohérentes avec le point de départ de SITL. -->
    <spherical_coordinates>
      <latitude_deg>-35.363262</latitude_deg>
      <longitude_deg>149.165237</longitude_deg>
      <elevation>584</elevation>
      <heading_deg>0</heading_deg>
      <surface_model>EARTH_WGS84</surface_model>
    </spherical_coordinates>

    <light type="directional" name="eclairage">
      <cast_shadows>false</cast_shadows>
      <pose>0 0 10 0 0 0</pose>
      <diffuse>0.8 0.8 0.8 1</diffuse>
      <specular>0.2 0.2 0.2 1</specular>
      <direction>-0.3 0.1 -0.9</direction>
    </light>

    <!-- Sol : emprise de la volière. -->
    <model name="sol">
      <static>1</static>
      <link name="link">
        <collision name="collision">
          <geometry><plane><normal>0 0 1</normal><size>100 100</size></plane></geometry>
        </collision>
        {visuel_plan("visuel", f"{L / 2} {l / 2} 0 0 0 0", (v["longueur"], v["largeur"]), sol)}
      </link>
    </model>

    {m.sdf()}
    {modele_fenetre(cfg, hauteur_fenetre, plaque, textures)}
    {obstacles}
    {modele_blocage(r["blocage_visuel"])}
    {modele_robot(r, plaque, textures[r["aruco_id"]])}
    {modeles_drone(cfg)}
  </world>
</sdf>
"""
    chemin = sortie / "droneload_2027.sdf"
    chemin.write_text(monde, encoding="utf-8")
    return chemin


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=pathlib.Path, default=ICI / "terrain.yaml")
    parser.add_argument("--sortie", type=pathlib.Path, default=ICI / "genere")
    parser.add_argument("--hauteur-fenetre", type=float, default=None,
                        help="hauteur du centre de la fenêtre en mètres (défaut : terrain.yaml)")
    args = parser.parse_args()

    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    hauteur = args.hauteur_fenetre
    if hauteur is None:
        hauteur = cfg["fenetre"]["hauteur_centre"]
    chemin = generer(cfg, args.sortie.resolve(), hauteur)
    print(chemin)


if __name__ == "__main__":
    main()
