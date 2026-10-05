# Changelog

Chaque version publiée possède une entrée datée. Le tag `vVERSION`, le fichier
`VERSION` et cette entrée doivent correspondre pour autoriser la publication.

## [0.1.7] - 2026-10-05

### Rendu conforme aux mesures M2

- Correction des ombres : les opérateurs de sprites suivent désormais les
  règles de composition du code ARM original. L'ombre de Harrier ne devient
  plus une zone éclaircie.
- Conversion des couleurs conforme à la sortie RGB du moteur M2 : chaque
  composante vaut 34 fois sa valeur CRAM en intensité normale, 17 fois en ombre.
  Prise en charge du second banc de palette des sprites et du fond.
- Correction du découpage des petites cellules de sprites au bord gauche,
  selon le comportement mesuré dans M2.
- Suppression de l'ancienne moyenne entre deux images du fond et du mécanisme
  optionnel de persistance des sprites. Le cœur fournit chaque image brute ;
  les alternances de pixels et de couleurs sont conservées.

### Sauvegardes instantanées

- Sauvegarde de la totalité de la mémoire graphique MDP et de l'historique du
  filtre audio. Après rechargement, SH1 et SH2 reproduisent exactement les
  180 images et le son des séquences de contrôle, avec les réglages par défaut.
- Les états des versions précédentes sont incompatibles ; relancer la ROM.

### Validation et limites

- Zéro différence sur 82 240 pixels indexés, à état vidéo identique : une image
  entière du stage 4 de SH2 (320 × 224), et 11 lignes supplémentaires par scène
  dans les stages 1 et 3 de SH2 et une scène de SH1. Référence obtenue en exécutant
  le moteur ARM original, avec contrôle séparé de sa conversion de couleurs.
- Oracles publics sans ROM : 208 cas de composition et 4 115 cas de conversion
  de couleurs ; tests du C++ réellement distribué et test de sauvegarde/reprise.
- 71 tests automatiques réussis, références ARM fraîches et ROM originales
  privées incluses dans la validation locale.
- 39 020 images rejouées sur six parcours SH1/SH2 ; son identique à la référence
  0.1.5 sur ces parcours. Les images changent avec les corrections ci-dessus.
- Ces mesures ne prouvent pas encore l'équivalence du minutage, des limites de
  sprites, de tous les hooks du jeu ni de tous les stages. Les filtres de
  présentation GPU de l'application M2 restent hors de ce périmètre.

## [0.1.6] - 2026-10-05

### Perspective et sprites SH2

- Suppression du décalage de 53 lignes et de l'étirement artificiel du décor
  SH2 : les plans utilisent la transformation de la ligne affichée, comme M2.
  Cela rétablit leur position par rapport aux sprites, notamment dans les
  stages 1 et 4 où les objets paraissaient trop bas.
- Prise en charge des 64 registres directs MDP. Les registres des plans et du
  zoom des sprites choisissent leurs tables et leur activation explicitement.
  Le contenu d'une ancienne table ne peut plus activer un effet désactivé.
- Rendu des deux plans selon les coordonnées, dimensions, retournements,
  palettes et priorités M2, avec rebouclage ou limitation aux bords. Suppression
  des règles SH2 qui masquaient certaines lignes de montagnes et de plafond.
- Zoom vertical des sprites conforme aux calculs M2 : agrandissement permis,
  hauteur nulle invisible, différence verticale circulaire sur 10 bits.

### Validation et limites

- Comparaison du C++ distribué avec les sorties d'exécution ARM originales :
  68 cas d'adressage des registres, 30 cas de plans et les cas de géométrie,
  choix de table et réduction des sprites. Fixtures publiques sans ROM.
- Comparaisons de captures SH2 des stages 1, 3 et 4, de l'attraction et du
  classement, ainsi que des deux parcours SH1 de 6 000 trames. Le son est
  inchangé sur les séquences comparées. Les corrections de zoom peuvent
  également modifier certains sprites SH1 ; ses images ne sont pas annoncées
  identiques à la version précédente.
- Aucun filtre de scintillement ni persistance ajouté. Le minutage M2, les
  palettes étendues des sprites, certains cas de bord d'écran et la validation
  de l'ensemble des stages restent à approfondir.
- Les anciens états instantanés sont incompatibles avec les registres étendus ;
  démarrer depuis la ROM originale.

## [0.1.5] - 2026-10-05

### Correction SH2

- Restauration de la fenêtre d'accès direct à la mémoire vidéo basse. Les
  écritures qui reconstruisent la police du classement atteignent maintenant
  leur destination, avec mise à jour du cache des caractères.
- Suppression du remappage de police selon la palette. Les lettres du titre
  « RANKING LIST » et les initiales utilisent les tuiles écrites par le jeu,
  avec son animation d'apparition. Aucun remplacement de police dans la ROM.

### Validation et limites

- Cause vérifiée dans le code M2, la trace du bus et le contenu de la mémoire
  vidéo : les 3 040 octets écrits pour la police étaient auparavant perdus.
- Comparaison de séquences SH2 de titre, jeu, premier boss, classement et
  Yees Land. Le son est inchangé sur les séquences comparées.
- SH1 conserve les flux vidéo et audio complets des deux parcours de 6 000
  trames de référence. Aucun filtre anti-scintillement ajouté.
- Le décor qui persiste derrière le classement, la géométrie de certains
  niveaux et le minutage M2 restent à traiter. Cette version ne prétend pas
  valider tous les stages ni l'exécution interactive Windows/Linux.

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
