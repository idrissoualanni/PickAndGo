import cv2
import requests
import json
from ultralytics import YOLO

import os
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION ---
API_URL = os.getenv("URL_API", "")
if not API_URL:
    raise ValueError(" L'URL_API n'est pas définie dans le fichier .env !")
USER_ID = "Client_5"

model = YOLO("best.pt")

memoire_objets = {}   # Stocke les IDs présents à l'image
objets_payes = set()  # IDs définitivement facturés
solde_local = "..."   # Stocke le solde retourné par l'API

# Catalogue produits
produits_info = {
    "no label": {"nom": "Bouteille Naturelle", "prix": 500},
    "no cap": {"nom": "Bouteille Gazelle", "prix": 1000},
    "Confirm": {"nom": "Bouteille Eau Kirene", "prix": 250}
}

def envoyer_paiement_api(montant):
    """ Envoie les données à Google Sheets avec gestion des redirections """
    try:
        payload = {"userID": USER_ID, "montant": montant, "action": "achat"}
        # allow_redirects=True est obligatoire pour Google Apps Script
        response = requests.post(API_URL, json=payload, timeout=10, allow_redirects=True)
        
        if response.status_code == 200:
            res_data = response.json()
            if res_data.get("status") == "success":
                return res_data.get("nouveau_solde")
            else:
                print(f" Refus API : {res_data.get('message')}")
        else:
            print(f" Erreur Serveur : {response.status_code}")
    except Exception as e:
        print(f" Erreur de connexion : {e}")
    return None

cap = cv2.VideoCapture(0)
print("--- SYSTÈME PICK & GO : CLOUD CONNECTÉ ---")

while True:
    ret, frame = cap.read()
    if not ret: break

    # 1. Tracking des objets
    results = model.track(frame, persist=True, conf=0.5)
    objets_actuels_visibles = set()
    
    if results[0].boxes and results[0].boxes.id is not None:
        boxes = results[0].boxes.xyxy.int().tolist()
        ids = results[0].boxes.id.int().tolist()
        clss = results[0].boxes.cls.int().tolist()

        for box, id_objet, classe in zip(boxes, ids, clss):
            nom_tech = str(model.names[classe]) # type: ignore
            
            if nom_tech in produits_info and id_objet not in objets_payes:
                memoire_objets[id_objet] = nom_tech
                objets_actuels_visibles.add(id_objet)
                
                # Dessiner le rectangle pour voir ce qui se passe
                x1, y1, x2, y2 = box
                nom_reel = produits_info[nom_tech]["nom"]
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, f"{nom_reel} ID:{id_objet}", (x1, y1-10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    # 2. Détection de sortie (Paiement)
    ids_en_memoire = set(memoire_objets.keys())
    objets_partis = ids_en_memoire - objets_actuels_visibles
    
    for id_parti in objets_partis:
        if id_parti not in objets_payes:
            nom_tech = memoire_objets[id_parti]
            prix = int(produits_info[nom_tech]["prix"]) # type: ignore
            
            print(f" Facturation ID {id_parti} : {prix} FCFA...")
            nouveau_solde = envoyer_paiement_api(prix)
            
            if nouveau_solde is not None:
                solde_local = nouveau_solde
                objets_payes.add(id_parti) # Ne plus jamais facturer cet ID
                print(f" Payé ! Nouveau solde : {solde_local} F")
        
        # Supprimer de la mémoire temporaire
        memoire_objets.pop(id_parti, None)

    # 3. Interface (HUD)
    cv2.rectangle(frame, (0, 0), (350, 60), (255, 0, 0), -1)
    cv2.putText(frame, f"SOLDE CLOUD: {solde_local} F", (15, 40), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    cv2.imshow("PICK & GO - SMART STORE", frame)
    
    if cv2.waitKey(1) & 0xFF == ord('q'): 
        break

cap.release()
cv2.destroyAllWindows()