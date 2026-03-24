"""
Configuration centrale de Pick & Go.
Toutes les classes de produits, leurs noms d'affichage et leurs prix en FCFA.
"""

PRODUCTS = {
    "Bouteille_Eau": {"nom": "Bouteille d'Eau",  "prix": 300},
    "Cahier":        {"nom": "Cahier",            "prix": 500},
    "Stylo":         {"nom": "Stylo",             "prix": 200},
    "Gazelle":       {"nom": "Bière Gazelle",     "prix": 800},
    "Choco_Pain":    {"nom": "Choco Pain",        "prix": 250},
    "Bissap":        {"nom": "Jus Bissap",        "prix": 400},
    "Riz":           {"nom": "Sac de Riz",        "prix": 1500},
    "Huile":         {"nom": "Huile",             "prix": 2000},
}

# Paramètres de détection
CONF_THRESHOLD  = 0.45
WARMUP_FRAMES   = 8
DISAPPEAR_FRAMES = 20
PROXIMITY_LIMIT = 130
IMG_SIZE_AI     = 320
