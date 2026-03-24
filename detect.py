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
import argparse
from pathlib import Path
from collections import defaultdict, Counter
from dotenv import load_dotenv
from ultralytics import YOLO

from config import (PRODUCTS, CONF_THRESHOLD, WARMUP_FRAMES, DISAPPEAR_FRAMES,
                    IMG_SIZE_AI, CAM_WIDTH, CAM_HEIGHT, VOTE_RATIO)

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
        self.votes           = defaultdict(list)  # {id: [class, class, ...]} historique des votes
        self.disappear_count = defaultdict(int)   # {id: nb frames absent}
        self.confirmed       = {}                 # {id: class_name} objets confirmes
        self.paid_ids        = set()              # IDs deja factures

        self.panier_total  = 0
        self.solde_affiche = "---"

    def process_frame(self, frame):
        """Detecte, traque et facture les produits dans une frame."""
        # Redimensionner pour inference rapide
        small = cv2.resize(frame, (IMG_SIZE_AI, IMG_SIZE_AI))
        results = self.model.track(small, persist=True,
                                   conf=CONF_THRESHOLD, imgsz=IMG_SIZE_AI,
                                   verbose=False)
        visible_ids = set()
        sx = frame.shape[1] / IMG_SIZE_AI  # facteur echelle X
        sy = frame.shape[0] / IMG_SIZE_AI  # facteur echelle Y

        for r in results:
            if r.boxes is None or r.boxes.id is None:
                continue
            for box, cls_tensor, track_id_tensor in zip(
                r.boxes.xyxy, r.boxes.cls, r.boxes.id
            ):
                track_id   = int(track_id_tensor)
                class_name = self.model.names[int(cls_tensor)]

                if class_name not in PRODUCTS:
                    continue

                visible_ids.add(track_id)
                self.disappear_count[track_id] = 0

                if track_id not in self.paid_ids:
                    # Systeme de vote : enregistre la classe detectee
                    self.votes[track_id].append(class_name)
                    votes = self.votes[track_id]

                    # Verifier la coherence apres WARMUP_FRAMES frames
                    if len(votes) >= WARMUP_FRAMES:
                        top_class, top_count = Counter(votes).most_common(1)[0]
                        if top_count / len(votes) >= VOTE_RATIO:
                            self.confirmed[track_id] = top_class
                        else:
                            # Trop de confusion → reset
                            self.votes[track_id] = []

                # Remettre a l'echelle pour affichage
                x1 = int(box[0] * sx); y1 = int(box[1] * sy)
                x2 = int(box[2] * sx); y2 = int(box[3] * sy)

                display_class = self.confirmed.get(track_id, class_name)
                info  = PRODUCTS.get(display_class, PRODUCTS[class_name])
                color = COLOR_PAID if track_id in self.paid_ids else COLOR_BOX

                # Label avec confiance
                label = f"{info['nom']} — {info['prix']} FCFA"
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(frame, label, (x1, max(y1 - 8, 12)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

                # Barre de progression warmup
                if track_id not in self.paid_ids:
                    pct   = min(len(self.votes[track_id]) / WARMUP_FRAMES, 1.0)
                    bar_w = int((x2 - x1) * pct)
                    bar_color = (0, 255, 200) if track_id in self.confirmed else (0, 165, 255)
                    cv2.rectangle(frame, (x1, y2 + 4), (x1 + bar_w, y2 + 10), bar_color, -1)

        # Facturer les objets disparus
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

        # Forcer resolution basse pour plus de fluidite
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  CAM_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_HEIGHT)
        cap.set(cv2.CAP_PROP_FPS, 30)
        print(f"Camera {camera_index} — {CAM_WIDTH}x{CAM_HEIGHT}")
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
