"""
Pick & Go — Module de detection en temps reel.
Utilise YOLOv8 + webcam pour detecter les produits et declencher les paiements.

Usage:
    python detect.py              # webcam par defaut
    python detect.py --image photo.jpg  # tester sur une image
"""

import cv2
import requests
import os
import time
import argparse
from pathlib import Path
from collections import defaultdict
from dotenv import load_dotenv
from ultralytics import YOLO

from config import PRODUCTS, CONF_THRESHOLD, WARMUP_FRAMES, DISAPPEAR_FRAMES

load_dotenv()

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────
MODEL_PATH = Path(__file__).parent / "models" / "pick_and_go" / "weights" / "best.pt"
if not MODEL_PATH.exists():
    MODEL_PATH = Path(__file__).parent / "best(1).pt"
if not MODEL_PATH.exists():
    MODEL_PATH = Path(__file__).parent / "best.pt"

URL_API = os.getenv("URL_API", "")
USER_ID = os.getenv("USER_ID", "Client_5")

# Couleurs BGR
COLOR_BOX    = (0, 220, 80)
COLOR_HEADER = (30, 30, 30)
COLOR_TEXT   = (255, 255, 255)
COLOR_PAID   = (80, 80, 255)


class PickAndGoDetector:
    def __init__(self):
        print(f"Chargement du modele: {MODEL_PATH}")
        self.model = YOLO(str(MODEL_PATH))
        print(f"Classes: {list(self.model.names.values())}")

        # Etat du tracking
        self.frame_count     = defaultdict(int)   # {id: nb frames vu}
        self.disappear_count = defaultdict(int)   # {id: nb frames absent}
        self.confirmed       = {}                 # {id: class_name} objets confirmes
        self.paid_ids        = set()              # IDs deja factures

        self.panier_total  = 0
        self.solde_affiche = "---"

    def process_frame(self, frame):
        """Detecte, traque et facture les produits dans une frame."""
        results = self.model.track(frame, persist=True, conf=CONF_THRESHOLD, verbose=False)
        visible_ids = set()

        for r in results:
            if r.boxes is None or r.boxes.id is None:
                continue
            for box, cls_tensor, track_id_tensor in zip(
                r.boxes.xyxy, r.boxes.cls, r.boxes.id
            ):
                track_id  = int(track_id_tensor)
                class_id  = int(cls_tensor)
                class_name = self.model.names[class_id]

                if class_name not in PRODUCTS:
                    continue

                visible_ids.add(track_id)
                self.disappear_count[track_id] = 0

                # Warmup : confirmer apres N frames consecutives
                if track_id not in self.paid_ids:
                    self.frame_count[track_id] += 1
                    if self.frame_count[track_id] >= WARMUP_FRAMES:
                        self.confirmed[track_id] = class_name

                # Dessiner la boite
                x1, y1, x2, y2 = map(int, box)
                info   = PRODUCTS[class_name]
                label  = f"{info['nom']} — {info['prix']} FCFA"
                color  = COLOR_PAID if track_id in self.paid_ids else COLOR_BOX

                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(frame, label, (x1, y1 - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

                # Barre de warmup
                if track_id not in self.paid_ids:
                    pct   = min(self.frame_count[track_id] / WARMUP_FRAMES, 1.0)
                    bar_w = int((x2 - x1) * pct)
                    cv2.rectangle(frame, (x1, y2 + 4), (x1 + bar_w, y2 + 10),
                                  (0, 255, 200), -1)

        # Detecter les objets qui ont disparu
        for track_id in list(self.confirmed.keys()):
            if track_id not in visible_ids:
                self.disappear_count[track_id] += 1
                if (self.disappear_count[track_id] >= DISAPPEAR_FRAMES
                        and track_id not in self.paid_ids):
                    self._facturer(track_id, self.confirmed[track_id])
                    self.paid_ids.add(track_id)
                    del self.confirmed[track_id]

        self._draw_hud(frame)
        return frame

    def _facturer(self, track_id, class_name):
        """Envoie la transaction a l'API Google Sheets."""
        info  = PRODUCTS[class_name]
        prix  = info["prix"]
        nom   = info["nom"]
        print(f"  Facturation ID {track_id}: {nom} ({prix} FCFA)")

        if not URL_API:
            print("  [DEMO] URL_API non definie — paiement simule")
            self.panier_total += prix
            self.solde_affiche = "DEMO"
            return

        try:
            payload = {"userID": USER_ID, "produit": nom,
                       "montant": prix, "action": "achat"}
            r = requests.post(URL_API, json=payload, timeout=10)
            data = r.json()
            if data.get("status") == "success":
                self.solde_affiche = f"{data.get('nouveau_solde', '?')} FCFA"
                self.panier_total += prix
                print(f"  PAYE: {nom} | Solde: {self.solde_affiche}")
            else:
                print(f"  REFUSE: {data.get('message')}")
        except Exception as e:
            print(f"  ERREUR: {e}")

    def _draw_hud(self, frame):
        """Affiche le HUD en haut de l'image."""
        h, w = frame.shape[:2]
        cv2.rectangle(frame, (0, 0), (w, 55), COLOR_HEADER, -1)
        txt = (f"PICK & GO  |  Solde: {self.solde_affiche}"
               f"  |  Panier: {self.panier_total} FCFA"
               f"  |  [Q] Quitter")
        cv2.putText(frame, txt, (12, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLOR_TEXT, 2)

    def run_webcam(self, camera_index=0):
        """Lance la detection en temps reel depuis la webcam."""
        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            print(f"Impossible d'ouvrir la camera {camera_index}")
            return

        print("PICK & GO actif — appuie sur [Q] pour quitter")
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame = self.process_frame(frame)
            cv2.imshow("Pick & Go — Detection", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()
        print(f"\nSession terminee — Panier total: {self.panier_total} FCFA")

    def run_image(self, image_path):
        """Teste la detection sur une image fixe."""
        img = cv2.imread(str(image_path))
        if img is None:
            print(f"Image introuvable: {image_path}")
            return

        # Simule quelques frames pour declencher le warmup
        for _ in range(WARMUP_FRAMES + DISAPPEAR_FRAMES + 5):
            frame = img.copy()
            frame = self.process_frame(frame)

        cv2.imshow("Pick & Go — Test image", frame)
        out = Path("test_results") / Path(image_path).name
        out.parent.mkdir(exist_ok=True)
        cv2.imwrite(str(out), frame)
        print(f"Resultat sauvegarde: {out}")
        print("Appuie sur une touche pour fermer...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()


# ──────────────────────────────────────────────
# Point d'entree
# ──────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pick & Go — Detection YOLOv8")
    parser.add_argument("--image", type=str, default=None,
                        help="Chemin vers une image (sinon webcam)")
    parser.add_argument("--camera", type=int, default=0,
                        help="Index de la webcam (defaut: 0)")
    args = parser.parse_args()

    detector = PickAndGoDetector()

    if args.image:
        detector.run_image(args.image)
    else:
        detector.run_webcam(args.camera)
