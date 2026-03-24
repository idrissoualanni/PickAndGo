"""
Script de test du modele YOLOv8 - Pick and Go
Usage: python test_model.py <image>
       python test_model.py                  # utilise les images de test par defaut
"""

import sys
import os
from pathlib import Path
from ultralytics import YOLO

# Cherche le modele dans cet ordre de priorite
_base = Path(__file__).parent
_candidates = [
    _base / "best(1).pt",
    _base / "models" / "pick_and_go" / "weights" / "best.pt",
    _base / "best.pt",
]
MODEL_PATH = next((p for p in _candidates if p.exists()), _base / "best.pt")
CONFIDENCE = 0.4


def test_image(model, image_path):
    image_path = Path(image_path)
    print(f"\n--- Test: {image_path.name} ---")
    try:
        results = model(str(image_path.resolve()), conf=CONFIDENCE)
    except Exception as e:
        print(f"  Erreur: {e}")
        return
    result = results[0]

    if len(result.boxes) == 0:
        print("  Aucun produit detecte.")
        return

    for box in result.boxes:
        cls_id = int(box.cls[0])
        cls_name = model.names[cls_id]
        confidence = float(box.conf[0])
        print(f"  Detecte: {cls_name:20s} | Confiance: {confidence:.1%}")

    # Sauvegarder l'image annotee
    out_dir = Path("test_results")
    out_dir.mkdir(exist_ok=True)
    result.save(filename=str(out_dir / Path(image_path).name))
    print(f"  Image annotee sauvegardee dans: test_results/{Path(image_path).name}")


def main():
    if not MODEL_PATH.exists():
        print(f"Modele introuvable: {MODEL_PATH}")
        print("Telecharge best.pt depuis Colab et place-le a la racine du projet.")
        sys.exit(1)

    print(f"Chargement du modele: {MODEL_PATH}")
    model = YOLO(str(MODEL_PATH))
    print(f"Classes: {list(model.names.values())}")

    # Images passees en argument ou image de test par defaut
    if len(sys.argv) > 1:
        images = sys.argv[1:]
    else:
        # Image de test incluse dans le projet
        default_img = Path(__file__).parent / "624440.webp"
        if default_img.exists():
            images = [default_img]
            print(f"Utilisation de l'image de test: {default_img.name}")
        else:
            # Cherche d'autres images dans le dossier courant
            extensions = ["*.jpg", "*.jpeg", "*.png", "*.webp", "*.jfif"]
            images = []
            for ext in extensions:
                images.extend(Path(".").glob(ext))

        if not images:
            print("\nAucune image trouvee. Usage:")
            print("  python test_model.py photo.jpg")
            sys.exit(0)

    for img in images:
        img = Path(img)
        if not img.exists():
            print(f"Image introuvable: {img}")
            continue
        # Ignore les fichiers avec accents ou espaces problematiques
        try:
            img.stat()
        except Exception:
            print(f"  Skip (nom de fichier problematique): {img.name}")
            continue
        test_image(model, img)

    print("\nTest termine.")


if __name__ == "__main__":
    main()
