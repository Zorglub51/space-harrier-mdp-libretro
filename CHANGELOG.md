# Changelog

Chaque version publiée possède une entrée datée. Le tag `vVERSION`, le fichier
`VERSION` et cette entrée doivent correspondre pour autoriser la publication.

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
