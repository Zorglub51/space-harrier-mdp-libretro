# Dépannage

## « Space Harrier MDP » n’apparaît pas

- Vérifiez que la bibliothèque est dans le dossier **Cœurs** et que
  `shmdp_libretro.info` est dans le dossier distinct **Informations sur les
  cœurs**, tels qu’indiqués dans **Paramètres > Répertoires**.
- Fermez RetroArch, supprimez `core_info.cache` du dossier **Informations sur les
  cœurs**, puis relancez RetroArch. Ce cache est automatiquement reconstruit.
- Vérifiez l’extension : `.dll` sous Windows, `.dylib` sous macOS, `.so` sous Linux.
- Vérifiez que vous avez téléchargé l’archive du bon système et de la bonne
  architecture.

## La ROM ne démarre pas

- Utilisez le fichier original non modifié de 4 063 232 octets.
- Vérifiez son SHA-1 : `e87e9338d7842db68a7a1e77bd5fc5b2bc8b2b72`.
- Chargez d’abord le cœur **Space Harrier MDP**, puis le fichier `.smp`.
- Activez **Paramètres > Journalisation > Niveau de journalisation : Debug**, puis
  relancez. Le journal doit contenir « Applied the Space Harrier MDP compatibility
  patch in memory ».

## macOS refuse de charger le cœur

Le cœur communautaire n’est pas signé par Apple. Dans **Réglages Système >
Confidentialité et sécurité**, autorisez l’ouverture si macOS affiche cette option.
Si RetroArch provient d’un paquet sandboxé, utilisez plutôt la version de bureau
officielle ou placez le cœur dans le dossier accessible à cette installation.

## Le jeu tourne trop vite ou trop lentement

Désactivez avance rapide, ralenti et rembobinage. Laissez la synchronisation audio
active et la fréquence d’images du cœur sur sa valeur normale.

## Signaler un bug

Indiquez le système, l’architecture, la version de RetroArch et la version du cœur.
Ajoutez le moment précis du jeu, une capture ou une courte vidéo et le journal
RetroArch. N’envoyez jamais la ROM.

### Plantages Windows des versions 0.1.16 et suivantes

Le signalement reste en cours d’analyse. Les contrôles réalisés et leurs limites
sont consignés dans [WINDOWS_RUNTIME_VALIDATION.json](https://github.com/Zorglub51/space-harrier-mdp-libretro/blob/main/docs/WINDOWS_RUNTIME_VALIDATION.json).

Extrayez la version concernée dans un nouveau dossier, puis lancez
`TESTER_SH1_WINDOWS.cmd` ou `TESTER_SH2_WINDOWS.cmd`. Sélectionnez votre RetroArch
x64 et la ROM originale. Le lanceur crée un dossier `session/` isolé, avec les
options par défaut et sans chargement automatique d’une sauvegarde. Conservez
vos sauvegardes et votre configuration habituelles.

Transmettez `logs/retroarch.log` et `session.json` de cette session, le code de
sortie affiché, les versions de Windows et RetroArch, le modèle du processeur,
le jeu et le moment du plantage. Si ce test fonctionne, indiquez aussi les
options utilisées lors du plantage initial. Si l’Observateur d’événements
Windows fournit une erreur d’application, ajoutez le module défaillant, le code
d’exception et le décalage de l’erreur. N’envoyez pas le dossier complet, les
ROMs ou les fichiers de sauvegarde.
