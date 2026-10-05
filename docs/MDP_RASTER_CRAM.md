# Adressage direct de la CRAM MDP

Le correctif rétablit la destination des écritures de couleur raster. SH1 écrit à
`0xC00400`, soit l'entrée 0 ; SH2 écrit à `0xC00462`, soit l'entrée `0x31`.
Le choix dépend de l'adresse, sans profil de jeu ni lecture de son état interne.

## Preuve issue du binaire M2

Binaire local de référence : SHA-256
`2374ddca2241d2a040f587a1e86359c3d3d5f1dc93e566588b35e15bee73178f`.
Le gestionnaire d'écriture MDP commence à l'offset fichier `0xB2CA8`, chargé à
`0xC2CA8` dans l'import ELF Ghidra utilisé ici.

Il reconnaît exactement la plage `0xC00400..0xC004FF`. Pour une écriture de mot
alignée, le chemin à `0xC2EB2` extrait les bits 1 à 7 de l'adresse (`UBFX` à
`0xC2EB8`), puis écrit le mot de données dans `CRAM[(adresse >> 1) & 0x7F]`.
L'ancien test du seul bit 10 était trop large et la destination fixe 0 perdait
l'index utilisé par SH2.

`tests/fixtures/mdp_cram_m2.json` contient dix observations sur des entrées
synthétiques, obtenues en exécutant les instructions ARM originales avec le
`PcodeEmulator` de Ghidra. Sept cas couvrent les entrées 0, 1, `0x31`, `0x3F`,
`0x40`, `0x7F` et un mot `0xFFFF`. Trois adresses hors plage s'arrêtent avant le
décodage des ports ordinaires, sans écriture CRAM directe. La fixture ne contient
aucun code exécutable M2 ni donnée de jeu.

## Portée et limite temporelle

Le port conserve sa datation préexistante à `vpos + 1`, avec retour à la ligne 0
pendant le retour vertical. **Cette convention temporelle n'est pas prouvée par
l'oracle d'adressage.** Le test ARM valide la plage, l'index et le mot écrit ; il
ne reproduit pas l'ordonnancement des lignes vidéo de M2.

Les écritures en attente sont séparées par ligne et par entrée CRAM. Plusieurs
couleurs peuvent donc changer pendant un même HBlank ; pour une même entrée et
une même ligne, la dernière valeur remplace les précédentes. Le reset efface les
validités et MAME sérialise les valeurs et validités en attente.

Ce correctif n'ajoute ni moyenne de deux images ni persistance de sprites. Il ne
règle pas les polices du classement ni les autres questions de géométrie SH2.

## Reproduction

La suite publique compile directement la méthode `vdp_mdp_w`, le préfixe de
rendu qui applique les couleurs et les déclarations de tableaux extraits du
patch distribué. Les seuls substituts sont l'écran, les ports VDP ordinaires et
la destination CRAM observée. Elle couvre les 128 destinations, les écritures
multiples, l'écrasement du même index, les bornes de lignes, le reset et les
masques transmis aux ports ordinaires.

```sh
python3 -m unittest discover -s tests -p test_mdp_raster_cram.py -v
```

Pour régénérer les observations, importer le binaire local dans un projet Ghidra
ARM ELF sans analyse, puis lancer le script fourni sur ce projet. Adapter les
chemins de Ghidra et du projet à l'installation locale :

```sh
/path/to/ghidra/support/analyzeHeadless /path/to/projects MdpReference \
  -process m2engage -noanalysis -readOnly \
  -scriptPath scripts/ghidra -postScript MdpCramOracle.java /tmp/mdp-cram-m2.json
MDP_CRAM_ORACLE_JSON=/tmp/mdp-cram-m2.json \
  python3 -m unittest discover -s tests -p test_mdp_raster_cram.py -v
```

Le script vérifie l'identité SHA-256 du binaire, sa correspondance d'adresse et
l'entrée du gestionnaire avant exécution. La commande Ghidra peut retourner un
code nul même après une erreur de script : vérifier le message final, le fichier
JSON produit, puis exécuter le test avec `MDP_CRAM_ORACLE_JSON`.
