"""
Collecte d'images pour l'entraînement YOLO.
Télécharge ~80 images par classe via Bing Image Search.

Usage:
    python scripts/collect_images.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from icrawler.builtin import BingImageCrawler
from config import PRODUCTS

IMAGES_PER_CLASS = 80

SEARCH_QUERIES = {
    "Bouteille_Eau": "bouteille eau minerale plastique transparent",
    "Cahier":        "cahier scolaire spirale lignes",
    "Stylo":         "stylo bille bleu noir ecriture",
    "Gazelle":       "gazelle biere bouteille senegal",
    "Choco_Pain":    "pain au chocolat viennoiserie boulangerie",
    "Bissap":        "bissap jus hibiscus sachet boisson senegal",
    "Riz":           "sac riz 5kg grains senegal",
    "Huile":         "huile cuisine bouteille jaune litre",
}


def collect():
    raw_dir = ROOT / "data" / "raw"
    print(f"[INFO] Dossier de collecte : {raw_dir}\n")

    for class_name in PRODUCTS:
        save_dir = raw_dir / class_name
        save_dir.mkdir(parents=True, exist_ok=True)

        existing = list(save_dir.glob("*.*"))
        if len(existing) >= IMAGES_PER_CLASS:
            print(f"  [OK] {class_name}: deja {len(existing)} images, ignore.")
            continue

        query = SEARCH_QUERIES[class_name]
        print(f"[DL] [{class_name}] Recherche: \"{query}\"")

        crawler = BingImageCrawler(
            feeder_threads=2,
            parser_threads=2,
            downloader_threads=4,
            storage={"root_dir": str(save_dir)},
        )
        crawler.crawl(keyword=query, max_num=IMAGES_PER_CLASS, min_size=(100, 100))

        downloaded = list(save_dir.glob("*.*"))
        print(f"  -> {len(downloaded)} images telechargees pour {class_name}\n")

    print("[DONE] Collecte terminee !")


if __name__ == "__main__":
    collect()
