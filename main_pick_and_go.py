import cv2
import requests
import os
from dotenv import load_dotenv
from ultralytics import YOLO

load_dotenv()

# 1. Charger ton modèle
model = YOLO("best.pt")

# 2. Configuration du compte et mémoire
URL_API = os.getenv("URL_API", "")
if not URL_API:
    raise ValueError(" L'URL_API n'est pas définie dans le fichier .env !")
USER_ID = "Client_5"

panier_total = 0
solde_affiche = "---"
memoire_objets = {}  # Stocke {id: nom_technique} pendant qu'ils sont à l'écran
objets_payes = set()  # Liste des IDs déjà facturés pour éviter les doubles paiements

# Dictionnaire des produits
produits_info = {
    "no label": {"nom": "Bouteille Naturelle", "prix": 500},
    "no cap": {"nom": "Bouteille Gazelle", "prix": 1000},
    "Confirm": {"nom": "Bouteille Eau Kirene", "prix": 250}
}

cap = cv2.VideoCapture(0)

print("--- PICK & GO : SYSTÈME BOUTEILLE ACTIVÉ (Appuyez sur 'q' pour quitter) ---")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # 3. Détection avec tracking
    results = model.track(frame, persist=True, conf=0.5)
    
    objets_actuels_visibles = set()
    
    for r in results:
        if r.boxes and r.boxes.id is not None:
            ids = r.boxes.id.int().tolist()
            cls = r.boxes.cls.int().tolist()
            boxes = r.boxes.xyxy.int().tolist()

            for id_objet, classe, box in zip(ids, cls, boxes):
                nom_tech = str(model.names[classe]) # type: ignore
                
                if nom_tech in produits_info:
                    # On enregistre l'objet seulement s'il n'a jamais été payé
                    if id_objet not in objets_payes:
                        memoire_objets[id_objet] = nom_tech
                        objets_actuels_visibles.add(id_objet)
                        
                        # Dessin des infos à l'écran
                        info = produits_info[nom_tech]
                        x1, y1, x2, y2 = box
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        cv2.putText(frame, f"{info['nom']} (ID:{id_objet})", (x1, y1 - 10), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    # --- LOGIQUE DE PAIEMENT UNIQUE ---
    # On regarde quels IDs étaient là juste avant mais ne sont plus là maintenant
    ids_en_memoire = set(memoire_objets.keys())
    objets_partis = ids_en_memoire - objets_actuels_visibles
    
    for id_parti in objets_partis:
        # On vérifie encore une fois si l'ID n'est pas déjà dans la liste des payés
        if id_parti not in objets_payes:
            nom_tech_parti = memoire_objets[id_parti]
            info_produit = produits_info[nom_tech_parti]
            
            prix = int(info_produit["prix"]) # type: ignore
            nom_reel = str(info_produit["nom"])
            
            print(f" Facturation ID {id_parti} : {nom_reel} ({prix} F)...")
            try:
                payload = {"userID": USER_ID, "produit": nom_reel, "montant": prix, "action": "achat"}
                res = requests.post(URL_API, json=payload, timeout=10, allow_redirects=True)
                if res.status_code == 200:
                    data = res.json()
                    if data.get("status") == "success":
                        solde_affiche = f"{data.get('nouveau_solde')} F"
                        panier_total += prix
                        objets_payes.add(id_parti)
                        print(f" PAIEMENT VALIDÉ : {nom_reel} -> Nouveau solde: {solde_affiche}")
                    else:
                        print(f" REFUS API : {data.get('message')}")
                else:
                    print(f" ERREUR SERVEUR : {res.status_code}")
            except Exception as e:
                print(f" ERREUR CONNEXION : {e}")
        
        # On nettoie la mémoire temporaire
        memoire_objets.pop(id_parti, None)

    # --- INTERFACE VISUELLE (HUD) ---
    cv2.rectangle(frame, (0, 0), (640, 60), (200, 0, 0), -1)
    affichage = f"SOLDE: {solde_affiche} | PANIER: {panier_total} F"
    cv2.putText(frame, affichage, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    cv2.imshow("PICK & GO - SYSTEME BOUTEILLE", frame)

    # Bouton 'q' pour arrêter
    if cv2.waitKey(1) & 0xFF == ord('q'):
        print("--- ARRÊT DU SYSTÈME ---")
        break

cap.release()
cv2.destroyAllWindows()