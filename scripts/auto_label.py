"""
Annotation automatique YOLO à partir des images brutes collectées.
Crée une bounding box centrée (90% du cadre) pour chaque image,
puis divise en train/val (80/20).

Usage:
    python scripts/auto_label.py
"""

import sys
import shutil
import random
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from config import PRODUCTS

TRAIN_RATIO = 0.8
VALID_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".jfif"}


def write_label(path: Path, class_id: int):
    """Écrit un fichier label YOLO : bbox plein cadre normalisé."""
    path.write_text(f"{class_id} 0.5 0.5 0.9 0.9\n")


def split_and_label():
    raw_dir   = ROOT / "data" / "raw"
    train_img = ROOT / "data" / "train" / "images"
    train_lbl = ROOT / "data" / "train" / "labels"
    val_img   = ROOT / "data" / "val"   / "images"
    val_lbl   = ROOT / "data" / "val"   / "labels"

    for d in [train_img, train_lbl, val_img, val_lbl]:
        d.mkdir(parents=True, exist_ok=True)

    class_names = list(PRODUCTS.keys())
    total_train = total_val = 0

    for class_id, class_name in enumerate(class_names):
        class_dir = raw_dir / class_name
        if not class_dir.exists():
            print(f"⚠️  Dossier absent: {class_dir} — ignoré.")
            continue

        images = [f for f in class_dir.iterdir() if f.suffix.lower() in VALID_EXTENSIONS]
        random.shuffle(images)

        split = int(len(images) * TRAIN_RATIO)
        sets = [("train", images[:split], train_img, train_lbl),
                ("val",   images[split:], val_img,   val_lbl)]

        for set_name, subset, img_dst, lbl_dst in sets:
            for img in subset:
                stem = f"{class_name}_{img.stem}"
                shutil.copy2(img, img_dst / f"{stem}{img.suffix}")
                write_label(lbl_dst / f"{stem}.txt", class_id)

        n_train, n_val = split, len(images) - split
        total_train += n_train
        total_val   += n_val
        print(f"  ✓ {class_name:20s} → {n_train} train | {n_val} val")

    print(f"\n✅ Dataset prêt : {total_train} train | {total_val} val")


if __name__ == "__main__":
    split_and_label()
