import cv2
import requests
import json
from ultralytics import YOLO

import os
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION ---
IP_TELEPHONE = os.getenv("IP_TELEPHONE", "")
if not IP_TELEPHONE:
    raise ValueError(" L'IP_TELEPHONE n'est pas définie dans le fichier .env !")
ADRESSE_FLUX = f"http://{IP_TELEPHONE}:8080/video"

API_URL = os.getenv("URL_API", "")
if not API_URL:
    raise ValueError(" L'URL_API n'est pas définie dans le fichier .env !")

# Chargement du modèle YOLO
print(" Chargement de l'IA...")
model = YOLO("best.pt")

# Variables de session
memoire_objets = {}   # {id: nom_technique}
objets_payes = set()  # IDs déjà débités
solde_affiche = "---"

# Catalogue produits
produits_info = {
    "no label": {"nom": "Bouteille Naturelle", "prix": 500},
    "no cap": {"nom": "Bouteille Gazelle", "prix": 1000},
    "Confirm": {"nom": "Bouteille Eau Kirene", "prix": 250}
}

def envoyer_paiement_api(montant):
    """ Envoie le débit à Google Sheets """
    try:
        payload = {"montant": montant}
        # allow_redirects est obligatoire pour Google
        response = requests.post(API_URL, json=payload, timeout=10, allow_redirects=True)
        if response.status_code == 200:
            res_data = response.json()
            if res_data.get("status") == "success":
                return res_data.get("nouveau_solde")
            else:
                print(f" Erreur Cloud : {res_data.get('message')}")
    except Exception as e:
        print(f" Erreur connexion API : {e}")
    return None

# Connexion à la caméra du téléphone
print(f" Connexion au téléphone : {ADRESSE_FLUX}")
cap = cv2.VideoCapture(ADRESSE_FLUX)

if not cap.isOpened():
    print(" Erreur : Impossible d'ouvrir le flux vidéo.")
    print("Vérifie que l'IP est correcte et que IP Webcam est lancé.")
    exit()

print(" Système démarré ! Appuyez sur 'q' pour quitter.")

while True:
    ret, frame = cap.read()
    if not ret: break

    # 1. Analyse YOLO avec Tracking
    results = model.track(frame, persist=True, conf=0.5)
    visibles_maintenant = set()

    if results[0].boxes and results[0].boxes.id is not None:
        boxes = results[0].boxes.xyxy.int().tolist()
        ids = results[0].boxes.id.int().tolist()
        clss = results[0].boxes.cls.int().tolist()

        for box, id_obj, cls in zip(boxes, ids, clss):
            nom_tech = str(model.names[cls]) # type: ignore
            
            if nom_tech in produits_info and id_obj not in objets_payes:
                memoire_objets[id_obj] = nom_tech
                visibles_maintenant.add(id_obj)
                
                # Dessin
                info = produits_info[nom_tech]
                x1, y1, x2, y2 = box
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, f"{info['nom']} #{id_obj}", (x1, y1-10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    # 2. Détection de Sortie (Paiement)
    # Si un ID était connu mais n'est plus visible = Achat effectué
    ids_en_memoire = set(memoire_objets.keys())
    objets_sortis = ids_en_memoire - visibles_maintenant

    for id_p in objets_sortis:
        if id_p not in objets_payes:
            nom_p = memoire_objets[id_p]
            prix_p = int(produits_info[nom_p]["prix"]) # type: ignore
            
            print(f" Paiement détecté : {nom_p} ({prix_p} F)")
            nouveau_solde = envoyer_paiement_api(prix_p)
            
            if nouveau_solde is not None:
                solde_affiche = f"{nouveau_solde} F"
                objets_payes.add(id_p)
                print(f" Nouveau solde Cloud : {solde_affiche}")
        
        # Nettoyage mémoire
        memoire_objets.pop(id_p, None)

    # 3. HUD (Interface)
    cv2.rectangle(frame, (0, 0), (350, 60), (255, 0, 0), -1)
    cv2.putText(frame, f"SOLDE CLOUD: {solde_affiche}", (20, 40), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    cv2.imshow("PICK & GO - SMART STORE", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()