# Changelog

Chaque version publiée possède une entrée datée. Le tag `vVERSION`, le fichier
`VERSION` et cette entrée doivent correspondre pour autoriser la publication.

## [0.1.4] - 2026-10-05

### Corrections SH2

- Restauration de `MOVE.L D4,D1` dans le générateur de lignes du décor :
  l'ancien `NOP` omettait la remise à -32 de la phase. La correction est
  établie par exécution du bloc ARM original de M2 sur 33 cas.
- Décodage des écritures directes de couleurs sur `C00400..C004FF` : chaque
  adresse sélectionne son entrée de palette, notamment `C00462` pour SH2.
  Plusieurs couleurs écrites pour une même ligne sont conservées séparément.
- Réinitialisation et sauvegarde des écritures de palette en attente.
- Ajout d'un lanceur Windows SH2 et des informations des deux ROM dans les
  guides. Le cœur reste commun à SH1 et SH2.

### Validation et limites

- Références d'exécution ARM et tests publics sans ROM pour le compteur de
  lignes et l'adressage des couleurs ; 39 000 trames SH2 réparties sur cinq
  scénarios comparées sur Mac, avec le premier boss atteint.
- SH1 conserve exactement les flux vidéo et audio complets sur deux
  parcours de 6 000 trames (attraction et commandes
  automatisées). Le correctif de palette ne change pas le son de SH2.
- Aucun filtre anti-scintillement ni persistance des sprites ajouté.
- Les caractères et le fond du classement SH2 restent incorrects ; la
  géométrie de certains décors demande encore une comparaison avec M2.
- L'équivalence complète du rendu et du minutage avec M2, les parties
  complètes et les essais interactifs Windows/Linux restent à valider.
- Les anciens états instantanés ne sont pas compatibles avec cette
  révision ; démarrer le jeu normalement depuis la ROM originale.

## [0.1.3] - 2026-10-05

### Corrections

- SH1 : les annonces de stages et de boss utilisent à nouveau les bons
  caractères. La compatibilité de police propre à SH2 est maintenant limitée à
  sa ROM originale reconnue.
- SH1 : correction de l'instruction de collision qui écrasait le compteur de
  parcours au niveau 1.
- SH2 : reconnaissance de la ROM originale dans le cœur, reconstruction des
  instructions, correction de la lecture des commandes et de la mémoire de
  couleurs étendue.
- Conservation des scintillements du fonctionnement testé ; aucun filtre
  anti-scintillement supplémentaire n'est activé.

### Téléchargements

- Archives complètes pour Windows x86_64, Linux x86_64, macOS Intel et macOS
  Apple Silicon, avec notices, informations du cœur et empreintes SHA-256.
- Lanceur de test SH1 pour Windows et installateur pour macOS.
- Sources correspondantes complètes, incluant la révision MAME épinglée,
  les patches et les outils de compilation. Aucune ROM n'est fournie.
- Publication des notes de cette version depuis ce changelog. Les versions
  suivantes utilisent le même mécanisme à la création d'un tag `vX.Y.Z`.

### Validation et limites

- Comparaison du premier bloc portable SH1 avec 31 cas mesurés dans le code ARM
  original de M2. Ce bloc reste testé séparément ; le cœur distribué utilise
  encore la reconstruction des instructions 68000.
- Vérification visuelle des textes SH1 sur Mac. Sur les parcours comparés de
  6 000 trames, SH2 conserve exactement les mêmes images et le même son ; le son
  de SH1 reste également identique.
- Tests automatiques des profils de ROM, de la reconstruction, des outils de
  publication et des archives. Compilation des quatre architectures avant
  publication.
- L'exécution interactive Windows et Linux et les parties complètes restent à
  valider. Les sauvegardes instantanées et la fidélité globale à M2 font encore
  l'objet de travaux.

### Utilisation

Téléchargez l'archive de votre système et extrayez-la avec 7-Zip ou un outil
compatible. Sous Windows, lancez `TESTER_SH1_WINDOWS.cmd` pour choisir RetroArch
x64 et votre ROM SH1 originale. Sur Mac, utilisez `INSTALLER_MACOS.command`.
Sous Linux, installez le `.so` et le `.info` selon le guide fourni.

L'archive `source` est destinée à la recompilation ; elle n'est pas nécessaire
pour jouer. Les fichiers `SHA256SUMS` servent à vérifier les téléchargements.

## [0.1.2] - 2026-10-05

Version de test locale, non publiée sur GitHub : correction de collision SH1,
première référence ARM mesurée et export Windows x64 avec lanceur de test.

## [0.1.1] - 2026-08-08

- Publication des cœurs Windows x86_64, Linux x86_64, macOS Intel et Apple Silicon.
- Installateur macOS et indications d'installation des informations du cœur.
- Archive des sources correspondantes.

[Historique détaillé de 0.1.1](https://github.com/Zorglub51/space-harrier-mdp-libretro/compare/v0.1.0...v0.1.1).
