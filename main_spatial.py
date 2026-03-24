"""
Pick & Go — Système de détection et de paiement automatique.
Utilise YOLOv8 + BoTSORT pour tracker personnes et produits en temps réel.
"""

import cv2
import math
import os
import time
import threading
import requests
from collections import defaultdict
from pathlib import Path
from ultralytics import YOLO
from dotenv import load_dotenv

from config import PRODUCTS, CONF_THRESHOLD, WARMUP_FRAMES, DISAPPEAR_FRAMES, PROXIMITY_LIMIT, IMG_SIZE_AI

load_dotenv()

URL_API       = os.getenv("URL_API", "")
IP_TELEPHONE  = os.getenv("IP_TELEPHONE", "")
USE_PHONE_CAM = bool(IP_TELEPHONE)
USER_ID       = "Client_5"

MODEL_PROD = Path(__file__).parent / "models" / "pick_and_go" / "weights" / "best.pt"
if not MODEL_PROD.exists():
    MODEL_PROD = Path(__file__).parent / "best.pt"

if not URL_API:
    raise ValueError("URL_API manquante dans le fichier .env !")
if USE_PHONE_CAM and not IP_TELEPHONE:
    raise ValueError("IP_TELEPHONE manquante dans le fichier .env !")


# ---------------------------------------------------------------------------
# Flux caméra en thread dédié
# ---------------------------------------------------------------------------

class CameraFeed:
    def __init__(self, source):
        self.source  = source
        self.cap     = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.ret, self.frame = self.cap.read()
        self.running = True
        threading.Thread(target=self._update, daemon=True).start()

    def _update(self):
        while self.running:
            if self.cap.isOpened():
                try:
                    ret, frame = self.cap.read()
                    if ret:
                        self.ret, self.frame = ret, frame
                    else:
                        self._reconnect()
                except Exception:
                    self._reconnect()
            else:
                time.sleep(1)

    def _reconnect(self):
        print("⚠️  Perte de flux — reconnexion dans 2s...")
        self.cap.release()
        time.sleep(2)
        self.cap = cv2.VideoCapture(self.source, cv2.CAP_FFMPEG)

    def read(self):
        return self.ret, self.frame

    def release(self):
        self.running = False
        self.cap.release()


# ---------------------------------------------------------------------------
# Moteur du magasin intelligent
# ---------------------------------------------------------------------------

class SmartStore:
    def __init__(self):
        print("🔄 Chargement des modèles IA...")
        self.model_pers = YOLO("yolov8n.pt")
        self.model_prod = YOLO(str(MODEL_PROD))
        self.products        = {}
        self.paid_ids        = set()
        self.recent_purchases = []
        self.session         = requests.Session()
        print("✅ Modèles chargés.\n")

    # ---- Dessin ----

    def _draw_label(self, img, text, pos, color):
        font, scale, thick = cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1
        (w, h), _ = cv2.getTextSize(text, font, scale, thick)
        x, y = pos
        cv2.rectangle(img, (x, y - h - 8), (x + w + 8, y), color, -1)
        cv2.putText(img, text, (x + 4, y - 4), font, scale, (255, 255, 255), thick)

    # ---- Paiement ----

    def _send_payment(self, name: str, price: int, uid: str):
        try:
            r = self.session.post(
                URL_API,
                json={"userID": uid, "produit": name, "montant": price, "action": "achat"},
                timeout=15,
                allow_redirects=True,
            )
            if r.status_code == 200:
                data = r.json()
                print(f"💳 {name} → {uid} | Nouveau solde : {data.get('nouveau_solde')} FCFA")
            else:
                print(f"❌ Erreur API ({r.status_code}): {r.text}")
        except Exception as e:
            print(f"❌ Connexion échouée : {e}")

    # ---- Traitement d'une frame ----

    def process_frame(self, frame):
        # 1. Détection personnes
        res_pers = self.model_pers.track(
            frame, persist=True, classes=[0], conf=0.4,
            imgsz=IMG_SIZE_AI, verbose=False, tracker="botsort.yaml"
        )[0]

        clients = {}
        if res_pers.boxes and res_pers.boxes.is_track:
            for box, pid in zip(res_pers.boxes.xyxy.int().tolist(),
                                res_pers.boxes.id.int().tolist()):
                x1, y1, x2, y2 = box
                center = ((x1 + x2) // 2, (y1 + y2) // 2)
                clients[pid] = center
                cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 120, 0), 2)
                self._draw_label(frame, USER_ID, (x1, y1), (255, 120, 0))

        # 2. Détection produits
        res_prod = self.model_prod.track(
            frame, persist=True, conf=CONF_THRESHOLD,
            imgsz=IMG_SIZE_AI, verbose=False, tracker="botsort.yaml"
        )[0]

        visible = set()
        if res_prod.boxes and res_prod.boxes.is_track:
            for box, oid, cls in zip(res_prod.boxes.xyxy.int().tolist(),
                                     res_prod.boxes.id.int().tolist(),
                                     res_prod.boxes.cls.int().tolist()):
                class_name = str(self.model_prod.names[cls])
                if class_name not in PRODUCTS or oid in self.paid_ids:
                    continue

                visible.add(oid)
                x1, y1, x2, y2 = box
                center = ((x1 + x2) // 2, (y1 + y2) // 2)

                p = self.products.setdefault(oid, {"pos": center, "type": class_name, "missing": 0, "stable": 0})
                p["pos"]     = center
                p["missing"] = 0
                p["stable"]  = p["stable"] + 1

                if p["stable"] >= WARMUP_FRAMES:
                    label = PRODUCTS[class_name]["nom"]
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 220, 0), 2)
                    self._draw_label(frame, label, (x1, y1), (0, 160, 0))

        # 3. Logique d'achat
        now = time.time()
        for oid in list(self.products):
            p = self.products[oid]
            if oid in visible:
                continue
            p["missing"] += 1
            if p["missing"] >= DISAPPEAR_FRAMES and p["stable"] >= WARMUP_FRAMES:
                class_name = p["type"]
                info       = PRODUCTS[class_name]
                last_pos   = p["pos"]

                nearest, min_dist = None, float("inf")
                for cid, cpos in clients.items():
                    d = math.dist(last_pos, cpos)
                    if d < min_dist:
                        min_dist, nearest = d, cid

                if nearest and min_dist < PROXIMITY_LIMIT:
                    self._send_payment(info["nom"], info["prix"], USER_ID)
                    self.paid_ids.add(oid)
                    self.recent_purchases.append({
                        "name": info["nom"], "price": info["prix"], "time": now
                    })
                self.products.pop(oid, None)

        # 4. Affichage des achats récents
        self.recent_purchases = [p for p in self.recent_purchases if now - p["time"] < 3]
        for i, p in enumerate(self.recent_purchases):
            cv2.putText(
                frame,
                f"ACHAT VALIDÉ : {p['name']} ({p['price']} FCFA)",
                (20, 40 + i * 35),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2,
            )

        return frame


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def main():
    store  = SmartStore()
    source = f"http://{IP_TELEPHONE}:8080/video" if USE_PHONE_CAM else 0
    print(f"📷 Source : {source}")

    cam = CameraFeed(source)
    time.sleep(2)

    if not cam.ret:
        print("❌ Flux indisponible. Vérifiez la caméra ou l'IP.")
        cam.release()
        return

    cv2.namedWindow("Pick & Go", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Pick & Go", 960, 540)
    print("--- SYSTÈME ACTIF  |  'q' pour quitter ---")

    while True:
        ret, frame = cam.read()
        if not ret or frame is None:
            time.sleep(0.05)
            continue

        frame = cv2.resize(frame, (960, 540))
        cv2.imshow("Pick & Go", store.process_frame(frame))
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cam.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
