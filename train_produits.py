"""
Entraînement du modèle YOLOv8 pour Pick & Go.

Workflow complet :
    1. python scripts/collect_images.py   # télécharge les images
    2. python scripts/auto_label.py       # crée les annotations YOLO
    3. python train_produits.py           # entraîne le modèle

Le modèle final est sauvegardé dans models/pick_and_go/weights/best.pt
"""

from pathlib import Path
from ultralytics import YOLO

ROOT      = Path(__file__).parent
DATA_YAML = ROOT / "data.yaml"
MODELS    = ROOT / "models"


def train(epochs: int = 50, batch: int = 4, imgsz: int = 320):
    print("Demarrage de l'entrainement Pick & Go...\n")

    model = YOLO("yolov8n.pt")

    results = model.train(
        data=str(DATA_YAML),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        workers=0,   # evite les crashes memoire sur CPU
        amp=False,   # desactive AMP (instable sur CPU)
        project=str(MODELS),
        name="pick_and_go",
        exist_ok=True,
        verbose=True,
    )

    best = MODELS / "pick_and_go" / "weights" / "best.pt"
    if best.exists():
        print(f"\n✅ Modèle prêt : {best}")
    else:
        print("\n⚠️  Modèle introuvable, vérifiez les logs ci-dessus.")

    return results


if __name__ == "__main__":
    train()
