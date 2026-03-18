import cv2
import requests
import math
import time
import numpy as np
import threading
from collections import defaultdict
from ultralytics import YOLO
import os
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION ---
URL_API = os.getenv("URL_API", "")
if not URL_API:
    raise ValueError(" L'URL_API n'est pas définie dans le fichier .env !")
USER_ID = "Client_5"

# Configuration Caméra Téléphone (IP Webcam)
USE_PHONE_CAM = True
IP_TELEPHONE = os.getenv("IP_TELEPHONE", "") 
if USE_PHONE_CAM and not IP_TELEPHONE:
    raise ValueError(" L'IP_TELEPHONE n'est pas définie dans le fichier .env !")
ADRESSE_FLUX = f"http://{IP_TELEPHONE}:8080/video"

class SmartStore:
    def __init__(self):
        print(" Initialisation des moteurs IA optimisés...")
        self.model_pers = YOLO("yolov8n.pt")
        self.model_prod = YOLO("best.pt")
        
        # Paramètres de performance
        self.PROXIMITY_LIMIT = 130    
        self.CONF_THRESHOLD = 0.45     
        self.IMG_SIZE_AI = 320        # RÉDUIT pour la vitesse (IA plus rapide)
        self.WARMUP_FRAMES = 8       
        self.DISAPPEAR_FRAMES = 20    
        # Mémoire
        self.products = {}      
        self.paid_ids = set()      
        self.session = requests.Session()
        self.recent_purchases = [] # Pour l'affichage visuel
        
        self.product_info = {
            "no label": {"nom": "Bouteille Naturelle", "prix": 500},
            "no cap": {"nom": "Bouteille Gazelle", "prix": 1000},
            "Confirm": {"nom": "Bouteille Eau Kirene", "prix": 250}
        }

    def draw_label(self, img, text, pos, bg_color):
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.45
        thickness = 1
        (w, h), _ = cv2.getTextSize(text, font, font_scale, thickness)
        x, y = pos
        cv2.rectangle(img, (x, y - h - 8), (x + w + 8, y), bg_color, -1)
        cv2.putText(img, text, (x + 4, y - 4), font, font_scale, (255, 255, 255), thickness)

    def process_frame(self, frame):
        # 1. Tracking Personnes
        res_pers = self.model_pers.track(frame, persist=True, classes=[0], conf=0.4, imgsz=self.IMG_SIZE_AI, verbose=False, tracker="botsort.yaml")[0]
        current_clients = {}
        if res_pers.boxes and res_pers.boxes.is_track:
            for box_xyxy, id_p in zip(res_pers.boxes.xyxy.int().tolist(), res_pers.boxes.id.int().tolist()):
                x1, y1, x2, y2 = box_xyxy
                center = ((x1 + x2) // 2, (y1 + y2) // 2)
                current_clients[id_p] = center
                cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 120, 0), 2)
                self.draw_label(frame, f"CLIENT {id_p}", (x1, y1), (255, 120, 0))

        # 2. Tracking Produits
        res_prod = self.model_prod.track(frame, persist=True, conf=self.CONF_THRESHOLD, imgsz=self.IMG_SIZE_AI, verbose=False, tracker="botsort.yaml")[0]
        visible_now = set()
        
        if res_prod.boxes and res_prod.boxes.is_track:
            for box_xyxy, id_o, cls in zip(res_prod.boxes.xyxy.int().tolist(), res_prod.boxes.id.int().tolist(), res_prod.boxes.cls.int().tolist()):
                tech_name = str(self.model_prod.names[cls]) # type: ignore
                if tech_name not in self.product_info or id_o in self.paid_ids: continue
                
                visible_now.add(id_o)
                x1, y1, x2, y2 = box_xyxy
                center = ((x1 + x2) // 2, (y1 + y2) // 2)
                
                if id_o not in self.products:
                    self.products[id_o] = {"pos": center, "type": tech_name, "missing": 0, "stable": 0}
                
                p = self.products[id_o]
                p["pos"] = center
                p["missing"] = 0
                s = int(p.get("stable", 0)) + 1 # type: ignore
                p["stable"] = s
                
                if s >= self.WARMUP_FRAMES:
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 220, 0), 2)
                    self.draw_label(frame, self.product_info[tech_name]["nom"], (x1, y1), (0, 160, 0))

        # 3. Logique d'Achat
        for id_o in list(self.products.keys()):
            if id_o not in visible_now:
                self.products[id_o]["missing"] += 1
                if self.products[id_o]["missing"] >= self.DISAPPEAR_FRAMES:
                    if int(self.products[id_o].get("stable", 0)) >= self.WARMUP_FRAMES: # type: ignore
                        last_pos = self.products[id_o].get("pos") # type: ignore
                        p_type = str(self.products[id_o].get("type")) # type: ignore
                        name = self.product_info[p_type]["nom"]
                        price = self.product_info[p_type]["prix"]
                        
                        best_client, min_dist = None, float('inf')
                        for cid, cpos in current_clients.items():
                            if last_pos is not None:
                                dist = math.dist(list(last_pos), list(cpos)) # type: ignore
                                if dist < min_dist:
                                    min_dist, best_client = dist, cid
                        
                        if best_client and min_dist < self.PROXIMITY_LIMIT:
                            print(f" [ID:{id_o}] {name} -> CLIENT {best_client} (OK: {int(min_dist)}px)")
                            self.send_payment(name, price, USER_ID)
                            self.paid_ids.add(id_o)
                            self.recent_purchases.append({"name": name, "price": price, "time": time.time()})
                    self.products.pop(id_o, None)
                    
        # 4. Affichage des achats récents à l'écran
        current_time = time.time()
        self.recent_purchases = [p for p in self.recent_purchases if current_time - p["time"] < 3.0]
        y_offset = 40
        for p in self.recent_purchases:
            text = f"ACHAT VALIDE: {p['name']} ({p['price']} FCFA)"
            cv2.putText(frame, text, (20, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            y_offset += 35
            
        return frame

    def _post_payment(self, item, amount, uid):
        try: self.session.post(URL_API, json={"userID": uid, "produit": item, "montant": amount, "action": "achat"}, timeout=3)
        except: pass

    def send_payment(self, item, amount, uid):
        # Utiliser un thread pour ne pas bloquer la vidéo pendant la requête HTTP (évite les lags)
        threading.Thread(target=self._post_payment, args=(item, amount, uid)).start()

class CameraFeed:
    def __init__(self, stream_url):
        self.stream_url = stream_url
        self.cap = cv2.VideoCapture(self.stream_url)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.ret, self.frame = self.cap.read()
        self.running = True
        self.thread = threading.Thread(target=self.update, daemon=True)
        self.thread.start()

    def update(self):
        while self.running:
            if self.cap.isOpened():
                try:
                    ret, frame = self.cap.read()
                    if ret:
                        self.ret, self.frame = ret, frame
                    else:
                        print(" Perte de flux... Reconnexion dans 2s")
                        self.cap.release()
                        time.sleep(2)
                        self.cap = cv2.VideoCapture(self.stream_url)
                except Exception as e:
                    print(f" Erreur OpenCV interceptée (instabilité réseau) : {e}")
                    self.cap.release()
                    time.sleep(2)
                    self.cap = cv2.VideoCapture(self.stream_url)
            else:
                time.sleep(1)

    def read(self):
        return self.ret, self.frame

    def release(self):
        self.running = False
        self.cap.release()

def main():
    store = SmartStore()
    
    stream_source = ADRESSE_FLUX if USE_PHONE_CAM else 0
    print(f" Connexion : {stream_source}")
    cap = CameraFeed(stream_source)
    
    # Attendre la première image
    time.sleep(2)
    if not cap.ret:
        print(" Flux indisponible. Vérifiez l'IP ou la caméra.")
        cap.release()
        exit()

    # Création de fenêtre explicite pour éviter le zoom
    cv2.namedWindow("Pick & Go - Flux Direct", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Pick & Go - Flux Direct", 960, 540)

    print("--- SYSTÈME FLUIDE ACTIVÉ ('q' pour quitter) ---")
    
    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            time.sleep(0.1)
            continue
            
        # Réduit le zoom en le forçant à une résolution plus petite
        frame = cv2.resize(frame, (960, 540))
        
        processed_frame = store.process_frame(frame)
        
        cv2.imshow("Pick & Go - Flux Direct", processed_frame)
        if cv2.waitKey(1) & 0xFF == ord('q'): break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
