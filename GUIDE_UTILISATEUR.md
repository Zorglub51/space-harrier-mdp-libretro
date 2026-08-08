# Guide utilisateur (français)

## Ce qu’il vous faut

1. Un ordinateur Windows 64 bits, macOS ou Linux 64 bits.
2. [RetroArch](https://www.retroarch.com/) installé.
3. Votre propre fichier original `jp_jp_space_harrier.smp`, extrait d’une Mega
   Drive Mini 2 vous appartenant.
4. L’archive `space-harrier-mdp-…zip` correspondant à votre système, téléchargée
   depuis la page **Releases** de ce dépôt.

La ROM n’est pas fournie. Le bon fichier fait exactement **4 063 232 octets** et
son SHA-1 est `e87e9338d7842db68a7a1e77bd5fc5b2bc8b2b72`.

## Installation dans RetroArch

1. Décompressez l’archive téléchargée.
2. Dans RetroArch, ouvrez **Paramètres > Répertoires** et notez le chemin indiqué
   pour **Cœurs** (ou *Cores*).
3. Fermez RetroArch.
4. Copiez les deux fichiers suivants dans ce dossier :
   - `shmdp_libretro.dll` sous Windows ;
   - `shmdp_libretro.dylib` sous macOS ;
   - `shmdp_libretro.so` sous Linux ;
   - et, dans tous les cas, `shmdp_libretro.info`.
5. Relancez RetroArch.

Sur certaines versions de RetroArch, vous pouvez aussi choisir **Charger un
cœur > Installer ou restaurer un cœur**, puis sélectionner directement la
bibliothèque extraite.

## Lancer le jeu

1. Choisissez **Charger un cœur**.
2. Sélectionnez **Space Harrier MDP**.
3. Choisissez **Charger du contenu**.
4. Sélectionnez votre fichier original `jp_jp_space_harrier.smp`.

C’est tout : le cœur reconnaît la ROM originale et applique les corrections en
mémoire. Il ne modifie jamais votre fichier `.smp`.

## Commandes conseillées

Le jeu utilise une manette standard :

- croix ou stick gauche : déplacer Harrier ;
- bouton **B** RetroPad : tirer ;
- **Start** : démarrer/mettre en pause selon l’écran.

Si le tir ne correspond pas au bouton souhaité, ouvrez le **Menu rapide >
Commandes > Commandes du port 1** et réaffectez le bouton.

## Vérifier que la ROM est la bonne

Ce contrôle est facultatif. Le cœur refusera simplement d’appliquer le correctif à
un fichier inconnu.

Sous Windows PowerShell :

```powershell
Get-FileHash -Algorithm SHA1 .\jp_jp_space_harrier.smp
```

Sous macOS ou Linux :

```bash
shasum jp_jp_space_harrier.smp
```

Le résultat attendu est `e87e9338d7842db68a7a1e77bd5fc5b2bc8b2b72`.

## En cas de problème

Consultez [Dépannage](docs/DEPANNAGE.md). Ne renommez pas un autre dump en
`.smp` : l’identification dépend du contenu, pas du nom du fichier.
