"""
Pick & Go — Detection temps reel avec proximite personne/produit.

Usage:
    python detect.py                    # webcam
    python detect.py --camera 1         # autre webcam
    python detect.py --phone 192.168.x.x  # camera telephone (IP Webcam)
    python detect.py --image photo.jpg  # test image fixe
"""

import cv2
import math
import os
import time
import threading
import argparse
from pathlib import Path
from collections import defaultdict, Counter
from dotenv import load_dotenv
from ultralytics import YOLO
import requests

from config import (PRODUCTS, CONF_THRESHOLD, WARMUP_FRAMES, DISAPPEAR_FRAMES,
                    IMG_SIZE_AI, CAM_WIDTH, CAM_HEIGHT, VOTE_RATIO,
                    PROXIMITY_LIMIT, SKIP_FRAMES)

load_dotenv()

URL_API = os.getenv("URL_API", "")
USER_ID = os.getenv("USER_ID", "Client_5")

MODEL_PROD = Path(__file__).parent / "models" / "pick_and_go" / "weights" / "best.pt"
if not MODEL_PROD.exists():
    MODEL_PROD = Path(__file__).parent / "best(1).pt"
if not MODEL_PROD.exists():
    MODEL_PROD = Path(__file__).parent / "best.pt"

# Couleurs BGR
C_PERSON  = (255, 140, 0)
C_PRODUCT = (0, 220, 80)
C_CONFIRM = (0, 200, 255)
C_PAID    = (80, 80, 255)
C_HUD     = (20, 20, 20)


# ─────────────────────────────────────────────
# Flux camera dans un thread dedie
# ─────────────────────────────────────────────

class CameraFeed:
    """Lit la camera en arriere-plan pour eviter les blocages."""

    def __init__(self, source):
        self.source  = source
        self.cap     = cv2.VideoCapture(source, cv2.CAP_FFMPEG
                       if isinstance(source, str) else cv2.CAP_ANY)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if isinstance(source, int):
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,  CAM_WIDTH)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_HEIGHT)
            self.cap.set(cv2.CAP_PROP_FPS, 30)
        self.ret, self.frame = self.cap.read()
        self.lock    = threading.Lock()
        self.running = True
        threading.Thread(target=self._update, daemon=True).start()

    def _update(self):
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                with self.lock:
                    self.ret, self.frame = ret, frame
            else:
                self._reconnect()

    def _reconnect(self):
        print("Perte de flux — reconnexion dans 2s...")
        self.cap.release()
        time.sleep(2)
        self.cap = cv2.VideoCapture(self.source)

    def read(self):
        with self.lock:
            return self.ret, self.frame.copy() if self.ret else (False, None)

    def release(self):
        self.running = False
        self.cap.release()


# ─────────────────────────────────────────────
# Moteur de detection
# ─────────────────────────────────────────────

class PickAndGoDetector:

    def __init__(self):
        print(f"Chargement modele produits : {MODEL_PROD}")
        self.model_prod = YOLO(str(MODEL_PROD))
        print("Chargement modele personnes : yolov8n.pt")
        self.model_pers = YOLO("yolov8n.pt")
        print(f"Classes produits : {list(self.model_prod.names.values())}\n")

        self.session = requests.Session()

        # Etat tracking produits
        self.votes           = defaultdict(list)  # {id: [classe, ...]}
        self.confirmed       = {}                 # {id: classe confirmee}
        self.prod_positions  = {}                 # {id: (cx, cy)}
        self.disappear_count = defaultdict(int)
        self.paid_ids        = set()

        # Etat tracking personnes
        self.clients         = {}                 # {id: (cx, cy)}

        # Paiements recents pour affichage
        self.recent_purchases = []

        self.panier_total  = 0
        self.solde_affiche = "---"
        self._frame_idx    = 0

    # ── Dessin ────────────────────────────────

    def _label(self, img, text, pos, color):
        f, sc, th = cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1
        (w, h), _ = cv2.getTextSize(text, f, sc, th)
        x, y = pos
        cv2.rectangle(img, (x, y - h - 8), (x + w + 8, y + 2), color, -1)
        cv2.putText(img, text, (x + 4, y - 3), f, sc, (255, 255, 255), th)

    # ── Paiement (thread separé pour ne pas bloquer) ──

    def _facturer(self, class_name, prod_pos):
        info = PRODUCTS[class_name]
        nom, prix = info["nom"], info["prix"]
        print(f"  Facturation: {nom} ({prix} FCFA)")

        if not URL_API:
            print("  [DEMO] Paiement simule")
            self.panier_total += prix
            self.solde_affiche = "DEMO"
            self.recent_purchases.append({"nom": nom, "prix": prix, "t": time.time()})
            return

        def _post():
            try:
                r = self.session.post(
                    URL_API,
                    json={"userID": USER_ID, "produit": nom,
                          "montant": prix, "action": "achat"},
                    timeout=12
                )
                data = r.json()
                if data.get("status") == "success":
                    self.solde_affiche = f"{data['nouveau_solde']} FCFA"
                    self.panier_total += prix
                    self.recent_purchases.append({"nom": nom, "prix": prix, "t": time.time()})
                    print(f"  PAYE: {nom} | Solde: {self.solde_affiche}")
                else:
                    print(f"  REFUSE: {data.get('message')}")
            except Exception as e:
                print(f"  ERREUR: {e}")

        threading.Thread(target=_post, daemon=True).start()

    # ── Traitement d'une frame ─────────────────

    def process_frame(self, frame):
        self._frame_idx += 1
        run_inference = (self._frame_idx % SKIP_FRAMES == 0)

        if run_inference:
            small = cv2.resize(frame, (IMG_SIZE_AI, IMG_SIZE_AI))
            sx    = frame.shape[1] / IMG_SIZE_AI
            sy    = frame.shape[0] / IMG_SIZE_AI

            # ── Detection personnes ──
            self.clients = {}
            res_p = self.model_pers.track(
                small, persist=True, classes=[0], conf=0.4,
                imgsz=IMG_SIZE_AI, verbose=False
            )[0]
            if res_p.boxes is not None and res_p.boxes.id is not None:
                for box, pid in zip(res_p.boxes.xyxy, res_p.boxes.id):
                    x1 = int(box[0]*sx); y1 = int(box[1]*sy)
                    x2 = int(box[2]*sx); y2 = int(box[3]*sy)
                    cx, cy = (x1+x2)//2, (y1+y2)//2
                    self.clients[int(pid)] = (cx, cy)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), C_PERSON, 2)
                    self._label(frame, USER_ID, (x1, y1), C_PERSON)

            # ── Detection produits ──
            visible_ids = set()
            res_pr = self.model_prod.track(
                small, persist=True, conf=CONF_THRESHOLD,
                imgsz=IMG_SIZE_AI, verbose=False
            )[0]

            if res_pr.boxes is not None and res_pr.boxes.id is not None:
                for box, cls_t, tid_t in zip(res_pr.boxes.xyxy,
                                             res_pr.boxes.cls,
                                             res_pr.boxes.id):
                    oid        = int(tid_t)
                    class_name = self.model_prod.names[int(cls_t)]
                    if class_name not in PRODUCTS or oid in self.paid_ids:
                        continue

                    visible_ids.add(oid)
                    self.disappear_count[oid] = 0

                    x1 = int(box[0]*sx); y1 = int(box[1]*sy)
                    x2 = int(box[2]*sx); y2 = int(box[3]*sy)
                    cx, cy = (x1+x2)//2, (y1+y2)//2
                    self.prod_positions[oid] = (cx, cy)

                    # Vote majoritaire
                    self.votes[oid].append(class_name)
                    votes = self.votes[oid]
                    if len(votes) >= WARMUP_FRAMES:
                        top_cls, top_n = Counter(votes).most_common(1)[0]
                        if top_n / len(votes) >= VOTE_RATIO:
                            self.confirmed[oid] = top_cls
                        else:
                            self.votes[oid] = []  # reset si confusion

                    # Dessin boite
                    color = C_CONFIRM if oid in self.confirmed else C_PRODUCT
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    disp_cls = self.confirmed.get(oid, class_name)
                    info     = PRODUCTS[disp_cls]
                    self._label(frame, f"{info['nom']} {info['prix']}F", (x1, y1), color)

                    # Barre de progression
                    pct   = min(len(votes) / WARMUP_FRAMES, 1.0)
                    bar_w = int((x2 - x1) * pct)
                    bar_c = (0, 200, 100) if oid in self.confirmed else (0, 140, 255)
                    cv2.rectangle(frame, (x1, y2+4), (x1+bar_w, y2+10), bar_c, -1)

                    # Ligne personne ↔ produit si proche
                    for cpos in self.clients.values():
                        dist = math.dist((cx, cy), cpos)
                        if dist < PROXIMITY_LIMIT:
                            cv2.line(frame, (cx, cy), cpos, (0, 255, 255), 1)

            # ── Facturation si produit disparu + personne proche ──
            for oid in list(self.confirmed.keys()):
                if oid in visible_ids:
                    continue
                self.disappear_count[oid] += 1
                if self.disappear_count[oid] >= DISAPPEAR_FRAMES and oid not in self.paid_ids:
                    last_pos = self.prod_positions.get(oid)
                    # Verifier proximite
                    proche = False
                    if last_pos and self.clients:
                        dist_min = min(math.dist(last_pos, cp) for cp in self.clients.values())
                        proche = dist_min < PROXIMITY_LIMIT
                    else:
                        proche = True  # si pas de detection personne, facturer quand meme

                    if proche:
                        self._facturer(self.confirmed[oid], last_pos)
                        self.paid_ids.add(oid)
                    del self.confirmed[oid]
                    self.votes.pop(oid, None)

        # ── Achats recents (3 secondes) ──
        now = time.time()
        self.recent_purchases = [p for p in self.recent_purchases if now - p["t"] < 3]
        for i, p in enumerate(self.recent_purchases):
            cv2.putText(frame, f"VALIDE : {p['nom']}  {p['prix']} FCFA",
                        (20, 75 + i * 32),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 80), 2)

        self._draw_hud(frame)
        return frame

    def _draw_hud(self, frame):
        h, w = frame.shape[:2]
        cv2.rectangle(frame, (0, 0), (w, 55), C_HUD, -1)
        txt = (f"PICK & GO  |  Solde: {self.solde_affiche}"
               f"  |  Panier: {self.panier_total} FCFA"
               f"  |  [Q] Quitter")
        cv2.putText(frame, txt, (12, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    # ── Modes de lancement ────────────────────

    def run_webcam(self, source=0):
        print(f"Camera: {source}")
        cam = CameraFeed(source)
        time.sleep(1)
        cv2.namedWindow("Pick & Go", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Pick & Go", CAM_WIDTH, CAM_HEIGHT)
        print("SYSTEME ACTIF — [Q] pour quitter")

        while True:
            ret, frame = cam.read()
            if not ret or frame is None:
                time.sleep(0.02)
                continue
            cv2.imshow("Pick & Go", self.process_frame(frame))
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

        cam.release()
        cv2.destroyAllWindows()
        print(f"\nSession terminee — Panier total: {self.panier_total} FCFA")

    def run_image(self, image_path):
        img = cv2.imread(str(image_path))
        if img is None:
            print(f"Image introuvable: {image_path}")
            return
        for _ in range(WARMUP_FRAMES + DISAPPEAR_FRAMES + 5):
            frame = self.process_frame(img.copy())
        out = Path("test_results") / Path(image_path).name
        out.parent.mkdir(exist_ok=True)
        cv2.imwrite(str(out), frame)
        print(f"Resultat: {out}")
        cv2.imshow("Pick & Go — Test", frame)
        cv2.waitKey(0)
        cv2.destroyAllWindows()


# ─────────────────────────────────────────────
# Point d'entree
# ─────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pick & Go — Detection YOLOv8")
    parser.add_argument("--image",  type=str, default=None, help="Image fixe")
    parser.add_argument("--camera", type=int, default=0,    help="Index webcam")
    parser.add_argument("--phone",  type=str, default=None,
                        help="IP telephone (ex: 192.168.1.10) — app IP Webcam")
    args = parser.parse_args()

    detector = PickAndGoDetector()

    if args.image:
        detector.run_image(args.image)
    elif args.phone:
        detector.run_webcam(f"http://{args.phone}:8080/video")
    else:
        detector.run_webcam(args.camera)
