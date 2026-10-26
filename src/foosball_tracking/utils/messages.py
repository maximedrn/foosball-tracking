"""Centralize display labels, console messages and application errors."""

from typing import Final

# Video overlays keep their formatting here; renderers supply measured values.
TABLE_LABEL: Final[str] = "BABY-FOOT"
BALL_DETECTED_LABEL: Final[str] = "BALLE DETECTEE"
BALL_NOT_DETECTED_LABEL: Final[str] = "BALLE NON DETECTEE"
BALL_ESTIMATED_LABEL: Final[str] = "BALLE ESTIMEE"
BALL_DETAILS_TEMPLATE: Final[str] = "BALLE C={circularity:.2f} r={radius:.1f}"
BALL_ESTIMATE_TEMPLATE: Final[str] = "ESTIMEE (+{missing_seconds:.2f}s)"
FRAME_COUNTER_TEMPLATE: Final[str] = "Image {frame_number}/{frame_count}"
DETECTION_RATE_TEMPLATE: Final[str] = (
    "Detection : {detected_frames}/{processed_frames} ({detection_rate:.1f} %)"
)
TRACKING_RATE_TEMPLATE: Final[str] = (
    "Estimation : {prediction_rate:.1f} % | Suivi : {coverage_rate:.1f} %"
)
PREVIEW_WINDOW_TITLE: Final[str] = "Suivi du baby-foot - Echap pour quitter"

# Command-line help describes the defaults and optional processing controls.
CLI_DESCRIPTION: Final[str] = (
    "Détecte le baby-foot et sa balle jaune dans une vidéo."
)
CLI_VIDEO_HELP: Final[str] = "vidéo source (video.mp4 par défaut)"
CLI_OUTPUT_HELP: Final[str] = "MP4 de sortie (output/tracking.mp4 par défaut)"
CLI_PREVIEW_HELP: Final[str] = "ouvre un aperçu ; Échap arrête le traitement"
CLI_MAX_FRAMES_HELP: Final[str] = "nombre maximal d'images à traiter"
CLI_CONFIG_HELP: Final[str] = (
    "lit les paramètres de détection et d'affichage dans un fichier JSON "
    "ou JSONC"
)

# Named placeholders keep callers independent of the displayed word order.
ERROR_MESSAGE_TEMPLATE: Final[str] = "Erreur : {error}"
PROCESSING_INTERRUPTED_MESSAGE: Final[str] = (
    "Traitement interrompu ; ressources vidéo libérées."
)
PROCESSED_FRAMES_TEMPLATE: Final[str] = "Images traitées : {processed_frames}"
DETECTION_SUMMARY_TEMPLATE: Final[str] = (
    "Balle détectée : {detected_frames} ({detection_rate:.1f} %)"
)
PREDICTION_SUMMARY_TEMPLATE: Final[str] = (
    "Balle estimée : {predicted_frames} ({prediction_rate:.1f} %)"
)
COVERAGE_SUMMARY_TEMPLATE: Final[str] = (
    "Balle détectée ou estimée : {coverage_rate:.1f} %"
)
OUTPUT_VIDEO_TEMPLATE: Final[str] = "Vidéo de sortie : '{path}'."
PROCESSING_PROGRESS_TEMPLATE: Final[str] = (
    "Images : {current}/{total} | balle : {detected_frames} "
    "({detection_rate:.1f} %) | estimation : {predicted_frames} "
    "({prediction_rate:.1f} %) | suivi : {coverage_rate:.1f} %"
)
UNKNOWN_FRAME_COUNT: Final[str] = "?"

# Video errors are shared by processing exceptions and their CLI presentation.
INPUT_OUTPUT_PATH_ERROR: Final[str] = (
    "Les chemins des vidéos source et de sortie doivent être différents."
)
EMPTY_VIDEO_ERROR: Final[str] = (
    "La vidéo source ne contient aucune image décodable."
)
INPUT_NOT_FOUND_ERROR_TEMPLATE: Final[str] = (
    "Vidéo source introuvable : '{path}'."
)
VIDEO_OPEN_ERROR_TEMPLATE: Final[str] = (
    "Impossible d'ouvrir la vidéo : '{path}'."
)
VIDEO_METADATA_ERROR: Final[str] = (
    "Les dimensions ou la fréquence d'images de la vidéo source sont invalides."
)
VIDEO_WRITER_ERROR_TEMPLATE: Final[str] = (
    "Impossible de créer la vidéo de sortie : '{path}'."
)

# Configuration validation reports invalid bounds before OpenCV is called.
RGB_BOUNDS_ERROR: Final[str] = (
    "Les bornes RGB doivent être ordonnées et comprises entre 0 et 255."
)
AREA_BOUNDS_ERROR: Final[str] = (
    "'maximum_area' doit être supérieur à 'minimum_area'."
)
RADIUS_BOUNDS_ERROR: Final[str] = (
    "'maximum_radius' doit être supérieur à 'minimum_radius'."
)
KERNEL_SIZE_ERROR: Final[str] = (
    "Les tailles des noyaux OpenCV doivent être impaires."
)
