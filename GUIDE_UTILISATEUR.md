# Guide utilisateur (français)

## Ce qu’il vous faut

1. Un ordinateur Windows 64 bits, macOS ou Linux 64 bits.
2. [RetroArch](https://www.retroarch.com/) installé.
3. Votre propre fichier original SH1 ou SH2, extrait d’une Mega Drive Mini 2
   vous appartenant.
4. L’archive `space-harrier-mdp-….7z` correspondant à votre système, téléchargée
   depuis la page **Releases** de ce dépôt.

Extrayez l'archive complète avec 7-Zip ou un outil compatible. Sur Mac,
choisissez `macos-arm64` pour Apple Silicon et `macos-x86_64` pour Intel.
L'archive `source` sert à recompiler et n'est pas nécessaire pour jouer.
Les changements de chaque version figurent dans les notes de la release et
dans le fichier `CHANGELOG.md` inclus.

Les ROM ne sont pas fournies. Le même cœur reconnaît les deux jeux :

| Jeu | Fichier original | Taille | SHA-1 |
| --- | --- | --- | --- |
| SH1 | `jp_jp_space_harrier.smp` | 4 063 232 octets | `e87e9338d7842db68a7a1e77bd5fc5b2bc8b2b72` |
| SH2 | `jp_jp_Space_Harrier_II.smp` | 3 670 016 octets | `80f576af01d6413c0b92073e2f947b0431f12a74` |

Sous Windows, `TESTER_SH1_WINDOWS.cmd` et `TESTER_SH2_WINDOWS.cmd` permettent
un essai avec choix de RetroArch et de la ROM. Chaque lancement conserve ses
journaux et captures dans un dossier de session distinct.

## Installation dans RetroArch

### macOS — installation automatique

1. Fermez complètement RetroArch.
2. Décompressez l’archive macOS.
3. Double-cliquez sur `INSTALLER_MACOS.command`. Si macOS le bloque, faites un
   clic droit sur le fichier puis choisissez **Ouvrir**.
4. Relancez RetroArch.

L’installateur lit les répertoires configurés par RetroArch, place chaque fichier
au bon endroit et régénère le cache des informations sur les cœurs. Il ne touche
ni aux ROM, ni aux sauvegardes, ni aux autres cœurs.

### Installation manuelle — tous les systèmes

1. Décompressez l’archive téléchargée.
2. Dans RetroArch, ouvrez **Paramètres > Répertoires** et notez les deux chemins
   indiqués pour **Cœurs** (ou *Cores*) et **Informations sur les cœurs**
   (ou *Core Info*).
3. Fermez RetroArch.
4. Copiez la bibliothèque dans le dossier **Cœurs** :
   - `shmdp_libretro.dll` sous Windows ;
   - `shmdp_libretro.dylib` sous macOS ;
   - `shmdp_libretro.so` sous Linux.
5. Copiez `shmdp_libretro.info` dans le dossier distinct **Informations sur les
   cœurs**. Ne le placez pas dans le dossier **Cœurs**.
6. Dans le dossier **Informations sur les cœurs**, supprimez le fichier généré
   `core_info.cache` s’il existe. RetroArch le recréera automatiquement.
7. Relancez RetroArch.

Sur une installation macOS standard, les emplacements sont généralement :

- bibliothèque : `~/Library/Application Support/RetroArch/cores/` ;
- fichier `.info` : `~/Library/Application Support/RetroArch/info/`.

Sur certaines versions de RetroArch, vous pouvez aussi choisir **Charger un
cœur > Installer ou restaurer un cœur**, puis sélectionner directement la
bibliothèque extraite. Cette commande n’installe pas toujours le fichier
`.info` et ne régénère pas toujours le cache : effectuez alors les étapes 5 et 6
manuellement.

## Lancer le jeu

1. Choisissez **Charger un cœur**.
2. Sélectionnez **Space Harrier MDP**.
3. Choisissez **Charger du contenu**.
4. Sélectionnez votre fichier original SH1 ou SH2 indiqué ci-dessus.

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
