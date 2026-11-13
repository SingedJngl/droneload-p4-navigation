#!/usr/bin/env bash
# Génère le monde DroneLoad 2027 puis lance Gazebo.
#
# Usage : sitl/lancer_gazebo.sh [--sans-ihm] [--hauteur-fenetre <m>]
#   --sans-ihm          serveur seul, rendu hors écran (caméra active, pas de fenêtre)
#   --hauteur-fenetre   hauteur du centre de la fenêtre E, tirée au hasard le jour J
set -euo pipefail

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARDUPILOT_GAZEBO="${ARDUPILOT_GAZEBO:-$HOME/ardupilot_gazebo}"

if [ ! -f "$ARDUPILOT_GAZEBO/build/libArduPilotPlugin.so" ]; then
  echo "Plugin ardupilot_gazebo introuvable dans $ARDUPILOT_GAZEBO/build." >&2
  echo "Indiquer son emplacement avec la variable ARDUPILOT_GAZEBO." >&2
  exit 1
fi

# Chemins fixés ici et non dans ~/.bashrc : le script marche aussi hors shell interactif.
export GZ_VERSION=harmonic
export GZ_SIM_SYSTEM_PLUGIN_PATH="$ARDUPILOT_GAZEBO/build:${GZ_SIM_SYSTEM_PLUGIN_PATH:-}"
export GZ_SIM_RESOURCE_PATH="$ARDUPILOT_GAZEBO/models:${GZ_SIM_RESOURCE_PATH:-}"

ihm=1
args_generateur=()
while [ $# -gt 0 ]; do
  case "$1" in
    --sans-ihm) ihm=0 ;;
    --hauteur-fenetre) args_generateur+=(--hauteur-fenetre "$2"); shift ;;
    *) echo "Option inconnue : $1" >&2; exit 1 ;;
  esac
  shift
done

monde="$(python3 "$ICI/gazebo/generer_monde.py" "${args_generateur[@]}")"

if [ "$ihm" -eq 1 ]; then
  exec gz sim -r "$monde"
else
  exec gz sim -s -r --headless-rendering "$monde"
fi
