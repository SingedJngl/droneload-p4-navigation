# Règles de contribution

## Branches

- `main` reste exécutable : tout ce qui y arrive se compile et passe les tests.
- Une branche par sujet, nommée `feat/…`, `fix/…`, `docs/…` ou `test/…`. Exemple : `feat/etat-recherche`.
- Fusion par pull request, relue par une autre personne que l'auteur. La règle est la même que pour les essais : personne ne valide son propre travail.

## Commits

Un commit fait une seule chose. Le message commence par un verbe à l'infinitif et dit ce qui change : `Ajouter la surveillance batterie à la machine à états`.

## Paramètres ArduPilot

Les fichiers `.parm` sont versionnés comme du code. Tout changement de paramètre sur le drone passe par un commit, afin de pouvoir revenir à un réglage qui volait.

## Essais

Chaque campagne d'essai porte un tag Git (`essai-AAAA-MM-JJ`). Le tag permet de retrouver le code et les paramètres exacts d'un résultat.

## Ce qui ne va pas dans le dépôt

- Rosbags, logs `.bin` de la Pixhawk, vidéos : trop lourds, ils vont sur le stockage partagé de l'équipe.
- Dossiers `build/`, `install/`, `log/` de colcon.
- Mots de passe, clés SSH, identifiants Wi-Fi. Le dépôt est public.
