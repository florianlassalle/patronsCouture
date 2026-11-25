# patron_vers_svg

Convertit un patron de couture **scanné** (PDF ou image), où plusieurs tailles sont dessinées en même temps avec des pointillés différents, en **SVG à calques** :

- un calque par taille, avec les pointillés remplacés par des **traits continus** ;
- un calque **Commun** qui contient tout ce qui est en trait plein (droit-fil, milieux, lignes communes, flèches, textes, crans) ;
- un calque **Non classé (à vérifier)**, masqué au départ, qui contient les petits morceaux que le programme n'a pas su attribuer à une taille.

Le SVG est à l'**échelle réelle** : une page A1 donne un SVG de 841 × 594 mm.

---

## Installation

Il faut **Python 3** (version 3.9 ou plus récente). Installez ensuite les bibliothèques, une seule fois :

```
pip install pymupdf opencv-python numpy scipy
```

---

## Utilisation

```
python patron_vers_svg.py MON_PATRON.pdf [options]
```

### Options

| Option | Rôle |
|---|---|
| `--pages 1,3` | Ne traite que les pages indiquées (par défaut : toutes). |
| `--exclure PAGE:x0,y0,x1,y1` | Zone de la page dont les pointillés vont dans le calque Commun, par exemple une légende ou un cartouche. L'option peut être répétée. Voir la section « Déterminer les proportions ». |
| `--separer` | Crée en plus un SVG par taille, qui contient le calque Commun et cette taille seulement. |
| `--sortie DOSSIER` | Dossier où enregistrer les SVG (par défaut : le dossier courant). |
| `--dpi 300` | Résolution de rendu. Laissez 300 : les réglages sont calibrés pour cette valeur. |

Le script accepte aussi une **image** (PNG, JPG…) à la place d'un PDF. Pour que les réglages restent valables, elle doit être scannée à 300 dpi.

### Exemple (patron Emma, La Maison Victor)

```
python patron_vers_svg.py Patron-A1.pdf --exclure 1:0.912,0.02,1,0.66 --exclure 2:0.88,0,1,0.12 --separer
```

Fichiers produits :

```
Patron-A1-page1.svg             ← toutes les tailles, un calque chacune
Patron-A1-page1-taille34.svg    ← avec --separer
...
Patron-A1-page2.svg
...
```

---

## Ouvrir le résultat dans Inkscape

1. Ouvrez le fichier SVG.
2. Ouvrez le panneau **Calques** avec `Ctrl+Maj+L`.
3. Masquez (icône en forme d'œil) les tailles qui ne vous servent pas.
4. Si vous voulez vérifier les morceaux non attribués, affichez le calque « Non classé ».

Couleurs des tailles : **34** rouge, **36** vert, **38** bleu, **40** orange, **42** violet.

Les lignes des tailles sont de vrais chemins. On peut les modifier avec l'outil Nœuds (touche `N`), changer leur épaisseur, etc.

---

## Déterminer les proportions pour `--exclure`

Une proportion, c'est la position d'un point divisée par la taille de la page. Les valeurs vont donc de 0 à 1 :
`x0,y0` est le coin **haut gauche** de la zone, `x1,y1` son coin **bas droit**.

### Avec Inkscape

1. Importez la page du PDF dans Inkscape.
2. Dessinez un rectangle (touche `R`) qui recouvre toute la zone à exclure.
3. Passez à l'outil Sélection (touche `S`) et mettez les unités en **mm** dans la barre du haut.
4. Relevez les valeurs **X**, **Y**, **L** (largeur) et **H** (hauteur) du rectangle.
   Dans Inkscape 1.x, l'origine est en haut à gauche, ce qui correspond au sens utilisé par le script.
5. Calculez, avec une page A1 paysage de 841 × 594 mm :

| Valeur | Calcul |
|---|---|
| x0 (bord gauche) | X ÷ 841 |
| y0 (bord haut) | Y ÷ 594 |
| x1 (bord droit) | (X + L) ÷ 841 |
| y1 (bord bas) | (Y + H) ÷ 594 |

Pour un autre format de page, remplacez 841 et 594 par la largeur et la hauteur de votre page.

### Exemple

La légende de la page 1 est recouverte par un rectangle placé à X = 767 mm et Y = 12 mm, qui mesure L = 74 mm sur H = 380 mm.

- x0 = 767 ÷ 841 = **0,912**
- y0 = 12 ÷ 594 = **0,02**
- x1 = (767 + 74) ÷ 841 = **1**
- y1 = (12 + 380) ÷ 594 = **0,66**

On obtient l'option `--exclure 1:0.912,0.02,1,0.66`. Le `1` avant les deux-points est le **numéro de la page**.

⚠️ En ligne de commande, utilisez un **point** comme séparateur décimal (`0.912`), pas une virgule.

### Avec un logiciel d'image (GIMP, Paint…)

Le principe est le même, en pixels : position du coin ÷ largeur ou hauteur de l'image.

### Conseil

Pas besoin d'être précis : il suffit que le rectangle englobe toute la zone, avec un peu de marge. Il ne doit simplement pas déborder sur les lignes du patron.

---

## Comment ça marche

1. Chaque page est rendue en image noir et blanc à 300 dpi.
2. Chaque petite tache noire, fine et allongée, est repérée comme un **tiret** ; les plus courtes comptent comme des **points**.
3. Les tirets **alignés et proches** sont reliés entre eux pour former des lignes.
4. Chaque ligne est attribuée à une taille d'après la **longueur de ses tirets et de ses espaces**.
5. Les coupures sont refermées. Aux croisements, la ligne est prolongée en ligne droite ; aux angles et aux pointes de pinces, les deux bouts sont prolongés jusqu'à leur point de rencontre.
6. Tout le reste va dans le calque Commun.

---

## Adapter à un autre patron

Les réglages correspondent à la légende du patron **La Maison Victor** (tailles 34 à 42). Les longueurs sont en pixels à 300 dpi (1 mm = 11,8 px) :

| Taille | Motif |
|---|---|
| 34 | points de 9, espaces de 8 |
| 36 | tirets de 51, espaces de 8 |
| 38 | tiret de 75, puis petit tiret de 19, espaces de 18 |
| 40 | tiret de 36, puis point de 11 (espaces de 7 et 35) |
| 42 | tirets de 51, espaces de 25 |

Pour un patron d'une autre marque :

1. Mesurez les tirets et les espaces de chaque taille dans la légende. Vous pouvez mesurer en mm dans Inkscape, puis multiplier par 11,8.
2. Ajustez les seuils de longueur dans les fonctions `classer_chaine()` et `tentative()` du script.
3. Si les tailles portent d'autres noms, modifiez aussi `TAILLES` et `COULEURS` en haut du fichier.

Autres réglages, en haut du script :

- `SEUIL_NOIR` : à augmenter si le scan est pâle, à diminuer s'il est grisâtre ou sale.
- `EPAISSEUR_TRAIT` : épaisseur des traits dans le SVG. 6 px correspond à environ 0,5 mm.

---

## Limites connues

- **Zones très chargées** (pointes de pinces, angles où toutes les tailles se croisent) : il peut manquer un petit bout de ligne, ou le raccord peut être approximatif. Vérifiez ces endroits et corrigez à la main si besoin.
- **Bords où toutes les tailles se superposent** : les pointillés y forment presque un trait plein, qui reste dans le calque Commun. C'est sans conséquence, puisque cette ligne est la même pour toutes les tailles.
- **Barres obliques des textes** (« MV / MDV ») : elles ressemblent à des tirets et se retrouvent dans le calque « Non classé ».
- Le script fonctionne sur des scans **en noir et blanc, propres**. Pour un scan en couleur où chaque taille a sa couleur, il vaut mieux séparer les couleurs (par exemple dans GIMP, avec *Sélection > Par couleur*).
- Si le PDF est **vectoriel** (les lignes sont sélectionnables une à une dans Inkscape), ce script ne sert à rien. Dans Inkscape, utilisez *Édition > Sélectionner même > Style de contour* pour isoler une taille, puis mettez un trait plein dans *Fond et contour*.
