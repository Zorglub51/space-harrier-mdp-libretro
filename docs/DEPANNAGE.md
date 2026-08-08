# Dépannage

## « Space Harrier MDP » n’apparaît pas

- Vérifiez que la bibliothèque et `shmdp_libretro.info` sont dans le dossier
  **Cœurs** indiqué par RetroArch.
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
