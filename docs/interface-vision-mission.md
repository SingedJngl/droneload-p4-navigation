# Contrat d'interface /vision vers /mission

Ce fichier fixe ce que le nœud de vision (P3) publie et ce que le nœud de mission (P4) attend. Il se modifie par pull request relue par les deux pôles, avant de toucher au code.

## Topic

| Champ | Valeur |
|---|---|
| Nom | `/vision/cible` |
| Type | `geometry_msgs/msg/PointStamped` |
| Contenu | écart cible − drone, en mètres |
| Repère (`header.frame_id`) | `map` (ENU) ou `base_link` |
| Horodatage | instant de la capture de l'image, pas de la publication |

## Règles

- Aucun message pendant 0,5 s signifie « cible non vue ». Le nœud de vision ne publie rien quand il ne détecte rien : il n'envoie pas de zéro.
- L'écart est en mètres, converti par la vision à partir de la hauteur mesurée. `/mission` ne reçoit jamais de pixels.

## À fixer

- Fréquence de publication minimale.
- Identité de la cible (ArUco, image A3) : le règlement 2027 impose de distinguer plusieurs cibles et des leurres, ce que `PointStamped` seul ne porte pas.
- Indice de confiance de la détection.
