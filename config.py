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
CONF_THRESHOLD   = 0.60   # plus haut = moins de faux positifs
WARMUP_FRAMES    = 12     # nb frames avant confirmation
DISAPPEAR_FRAMES = 15     # nb frames absent avant facturation
IMG_SIZE_AI      = 320    # taille inference (320 = rapide, 640 = precis)
CAM_WIDTH        = 960    # resolution webcam
CAM_HEIGHT       = 540
VOTE_RATIO       = 0.75   # 75% des frames doivent voter pour la meme classe
PROXIMITY_LIMIT  = 180    # distance max personne-produit pour declencher paiement
SKIP_FRAMES      = 3      # inference produit 1 frame sur N
PERSON_SKIP      = 8      # inference personne 1 frame sur N (bouge moins vite)
