
# Foosball Tracking

Détecte le terrain de baby-foot et suit les déplacements de la balle dans une vidéo à l'aide d'[OpenCV](https://opencv.org/). Aucun apprentissage automatique n'est nécessaire.

## Installation

```bash
uv sync --locked
```

## Utilisation

```bash
# Traiter les 300 premières images sans afficher d'aperçu.
uv run foosball video.mp4 --output output/extract.mp4 --max-frames 300

# Afficher un aperçu en direct pendant le traitement.
uv run foosball video.mp4 --output output/preview.mp4 --preview

# Utiliser un fichier de configuration personnalisé.
uv run foosball --config config.jsonc

# Définir le nombre de workers pour la détection parallèle de la balle.
uv run foosball --config config.jsonc --workers 4
```

## Fonctionnement

### 1. Détection du terrain

L'image est redimensionnée selon le facteur `table.scale` afin d'accélérer le traitement, puis convertie de BGR en RGB. Un masque de couleur, délimité par `table.rgb.lower` et `table.rgb.upper`, permet d'isoler la surface de jeu. Une fermeture morphologique relie les régions séparées à l'aide de `table.close_kernel_size` et `table.close_iterations`. Le plus grand contour est conservé s'il occupe au moins la proportion de l'image définie par `table.minimum_area_ratio`.

La fonction `cv2.minAreaRect` ajuste ensuite un rectangle orienté autour du contour, tout en préservant l'orientation du terrain. Les coordonnées d'origine sont rétablies, puis le rectangle est agrandi selon `table.box_expansion` pour délimiter l'ensemble de la table. Le terrain est détecté à nouveau à la fréquence définie par `table.detection_every`.

![Illustration de la détection du terrain](docs/field-detection.svg)

### 2. Détection de la balle

À chaque image, la détection est limitée au polygone du terrain. Après un flou gaussien (taille du noyau : `ball.blur_kernel_size`), un masque RGB défini par `ball.rgb.lower` et `ball.rgb.upper` identifie les balles potentielles. Les petits espaces sont comblés par une fermeture morphologique utilisant `ball.close_kernel_size`, avant l'extraction des contours.

Les candidats sont filtrés selon leur aire ($`A \in [A_{\min}, A_{\max}]`$), le rayon de leur cercle englobant ($`r \in [r_{\min}, r_{\max}]`$), leur rapport d'aspect, leur circularité et leur taux de remplissage. Ces seuils sont définis dans `config.jsonc` par `ball.minimum_area`, `ball.maximum_area`, `ball.minimum_radius`, `ball.maximum_radius`, `ball.maximum_aspect_ratio`, `ball.minimum_circularity` et `ball.minimum_fill_ratio`.

La circularité mesure à quel point un contour se rapproche d'un cercle :

$$
C = \frac{4\pi A}{P^2}
$$

où :

- $`A`$ est l'aire du contour (px²).
- $`P`$ est le périmètre du contour (px).
- $`C`$ est le score de circularité (sans unité).

Un cercle parfait possède une circularité $`C = 1`$, tandis que des valeurs plus faibles indiquent des formes de plus en plus irrégulières ou allongées.

![Illustration de la géométrie des candidats](docs/ball-geometry.svg)

Les candidats valides sont classés à l'aide d'un score pondéré :

$$
S = 4C + 3F + 2\max\left(0,\ 1-\frac{|r-r_{\mathrm{ref}}|}{r_{\mathrm{ref}}}\right)
$$

où :

- $`C`$ est le score de circularité.
- $`F = \dfrac{A}{\pi r^2}`$ est la fraction du cercle englobant minimal occupée par le contour.
- $`A`$ est l'aire du contour (px²).
- $`r`$ est le rayon du cercle englobant (px).
- $`r_{\mathrm{ref}}`$ est le rayon attendu de la balle (px), défini par `ball.expected_radius`.

Le score favorise les contours circulaires (poids 4), les contours qui remplissent leur cercle englobant (poids 3) et les candidats dont le rayon est proche de $`r_{\mathrm{ref}}`$ (poids 2). Ces coefficients sont fixes dans l'implémentation, tandis que le rayon attendu est configurable.

Le candidat obtenant le score le plus élevé est sélectionné comme balle. En cas d'égalité, le candidat dont le rayon est le plus proche de $`r_{\mathrm{ref}}`$ est privilégié.

![Illustration du calcul du score des candidats](docs/ball-scoring.svg)

### 3. Suivi de la balle

Le système de suivi estime la vitesse à partir de deux positions réellement observées de la balle, puis applique un lissage pour réduire le bruit :

$$
\mathbf{v}_t = \alpha\,\mathbf{v}_{\text{measured}} + (1-\alpha)\,\mathbf{v}_{t-1}
$$

où :

- $`\mathbf{v}_t`$ est la vitesse lissée à l'instant $`t`$.
- $`\mathbf{v}_{\text{measured}}`$ est la vitesse calculée à partir des deux dernières observations réelles de la balle.
- $`\mathbf{v}_{t-1}`$ est la vitesse lissée précédente.
- $`\alpha`$ est le coefficient de lissage, défini par `tracking.velocity_smoothing`.

![Illustration du lissage de la vitesse](docs/velocity-smoothing.svg)

Lorsque la balle est temporairement masquée, sa position est extrapolée à partir de la dernière position observée, selon un modèle à vitesse constante :

$$
\hat{\mathbf{p}}(\Delta t) = \mathbf{p}_{\text{last}} + \mathbf{v}_t\Delta t
$$

où :

- $`\hat{\mathbf{p}}(\Delta t)`$ est la position prédite après un intervalle de temps $`\Delta t`$.
- $`\mathbf{p}_{\text{last}}`$ est la dernière position de la balle observée visuellement.
- $`\mathbf{v}_t`$ est la dernière estimation de vitesse lissée.
- $`\Delta t`$ est le temps écoulé depuis la dernière observation réelle (secondes).

La prédiction est limitée à `tracking.maximum_prediction_seconds` secondes et s'arrête si le point estimé sort du terrain. Une nouvelle détection visuelle est toujours prioritaire ; les positions prédites ne sont jamais réutilisées comme observations.

![Illustration de la prédiction de position de la balle](docs/occlusion-prediction.svg)

Tous les seuils et paramètres de suivi peuvent être modifiés dans [`config.jsonc`](config.jsonc).

## Résultats de performance

![Résultats de performance](docs/performance.svg)

## Développement

```bash
# Formater les fichiers Python.
uv run ruff format .

# Vérifier le code avec Ruff.
uv run ruff check .

# Vérifier les types avec Pyright.
uv run pyright

# Vérifier les types avec MyPy.
uv run mypy

# Vérifier les erreurs avec Pylint.
uv run pylint --errors-only src scripts

# Construire le paquet.
uv build

# Générer tous les diagrammes.
uv run poe diagrams

# Supprimer tous les SVG des diagrammes générés.
uv run poe diagrams-clean

# Générer le rapport de performance à partir des vidéos testées.
uv run poe performance <REPORTS...> --output <OUTPUT.svg>
```
