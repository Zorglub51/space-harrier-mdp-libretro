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

## Mode Mark VI pour SH2

Dans **Menu rapide > Options du cœur > Emulation Hacks > SH2 Rendering**,
choisissez **Mark VI (Experimental)**. Le cœur reconstruit les morceaux de
sprites avant les quotas de 40/80 entrées du jeu, puis affiche une liste
extensible, sans quotas par ligne ni indices de liste/zoom limités à 128.
**Original (M2)** reste le réglage fidèle par défaut.

Le changement s'applique sans redémarrage. SH1 n'est pas affecté. Mark VI peut
être combiné avec Deflicker et les explosions SH1. Aucun patch ROM supplémentaire
n'est nécessaire et votre fichier ROM reste inchangé.

La vitesse du jeu et la cadence des animations restent celles d'origine.
Mark VI supprime les omissions dues à la capacité des listes et du rendu ;
il conserve les clignotements et les décisions de visibilité intentionnels.
Il n'ajoute pas d'objets au jeu ni d'images d'animation et ne propose pas encore
d'interpolation à 60/120 images/s. Afficher davantage de sprites peut demander
plus de calcul à l'ordinateur.

**Les états sauvegardés avec les anciennes versions ne sont pas compatibles
avec la 0.1.16.** Dans cette version, ils fonctionnent dans les deux modes ;
conservez le même choix pour obtenir un rendu identique après reprise.

## Options Deflicker natives

Dans **Menu rapide > Options du cœur > Emulation Hacks**, choisissez **SH1
Deflicker (Native)** ou **SH2 Deflicker (Native)**. Chaque jeu a son réglage :

- **Game Setting** (par défaut) : laisser le réglage interne du jeu décider.
- **OFF**, **ON1**, **ON2** : sélectionner directement la stratégie originale.

Le changement prend effet pendant la partie, sans redémarrage. ON1 et ON2 peuvent
réduire les scintillements, mais aussi omettre des sprites : ce sont les compromis
originaux. Aucun filtre d’image, mélange de trames ou effet de persistance n’est
ajouté. Le choix interne du jeu est conservé ; **Game Setting** lui rend la main.

Le choix du cœur s’applique aussi après un reset ou le chargement d’une sauvegarde
instantanée. Gardez le même réglage pour reproduire une séquence à l’identique.
Le format des sauvegardes reste inchangé, y compris le mode explosions SH1 de
la version 0.1.14.

## Explosions de SH1 dans SH2 — option facultative

Placez votre ROM originale `jp_jp_space_harrier.smp` à côté de celle de SH2,
ou dans le répertoire **System/BIOS** de RetroArch. Dans **Menu rapide >
Options du cœur > Emulation Hacks**, choisissez **SH1 Artwork and Timing**
pour **SH2 Explosions**. Le changement relance automatiquement SH2 depuis
le début lorsque vous reprenez le jeu. Le remplacement concerne tous les objets qui explosent : ennemis, boss,
décors et effets produits par les collisions du joueur. Il ne dépend plus
d’une liste de familles d’ennemis. La réservation des graphismes corrige aussi
les retours aux explosions d’origine dans le niveau 3.

Le réglage par défaut est **Original SH2**. Sélectionnez-le pour relancer
le jeu avec ses effets d’origine. Le cœur extrait les dessins et la palette
de votre ROM SH1 et reproduit sa cadence d’animation ; aucun fichier ROM n’est modifié. Si SH1 manque
ou ne correspond pas à la version attendue, l’animation originale est conservée
et un message vous en informe. Cette option n’affecte pas le jeu SH1.

Les sauvegardes instantanées sont propres au mode choisi : le cœur refuse
celles de l’autre mode. Les états du mode modifié créés avec les versions 0.1.12
et 0.1.13 ne sont pas compatibles avec la 0.1.14. Les sauvegardes automatiques MAME utilisent
un dossier séparé pour le mode modifié. Changer l’option commence une nouvelle
partie sans recharger une sauvegarde automatique.

Les explosions ordinaires descendent rapidement vers le sol dans SH2 d’origine
également. Le mod conserve les positions, les déplacements et les règles de
disparition de SH2, avec les dessins et la cadence des poses de SH1.

Ce mod facultatif est expérimental. Le temps pris par ses instructions peut
ralentir les effets denses : une rafale de boss contrôlée a retardé sa fin de
22 images vidéo, soit environ 0,37 seconde. Les particules de boss peuvent
disparaître avant d’afficher les onze poses de SH1, car elles gardent leur durée
de vie de SH2. Les mesures précédentes sur la 0.1.12 relevaient aussi de petits
écarts d’image dans l’introduction et d’échantillons audio ; une différence
audible n’a pas été établie. Gardez **Original SH2** pour retrouver le
comportement d’origine.

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
