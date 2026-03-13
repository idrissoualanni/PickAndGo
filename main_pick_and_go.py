import cv2
from ultralytics import YOLO

# 1. Charger ton modèle (assure-toi que le fichier est dans le même dossier)
model = YOLO("best.pt")

# 2. Configuration du compte et des produits
solde_client = 5000 
panier_total = 0
memoire_objets = {} # Pour se souvenir de quel produit correspond à quel ID

# Mise à jour : Remplacement de "Bissap" par "Bouteille"
produits_info = {
    "no label": {"nom": "Bouteille Naturelle", "prix": 500},
    "no cap": {"nom": "Bouteille", "prix": 1000},
    "Confirm": {"nom": "Bouteille Eau Kirene", "prix": 250}
}

cap = cv2.VideoCapture(0)

print("--- PICK & GO : SYSTÈME BOUTEILLE ACTIVÉ ---")

while True:
    ret, frame = cap.read()
    if not ret: break

    # 3. Détection avec tracking (persist=True est essentiel pour garder les IDs)
    results = model.track(frame, persist=True, conf=0.5)
    
    objets_actuels_visibles = set()
    
    for r in results:
        if r.boxes and r.boxes.id is not None:
            ids = r.boxes.id.int().tolist()
            cls = r.boxes.cls.int().tolist()
            boxes = r.boxes.xyxy.int().tolist()

            for id_objet, classe, box in zip(ids, cls, boxes):
                nom_tech = model.names[classe]
                
                if nom_tech in produits_info:
                    # On enregistre l'ID et son nom dans notre mémoire
                    memoire_objets[id_objet] = nom_tech
                    objets_actuels_visibles.add(id_objet)
                    
                    # Dessin du rectangle et affichage du nom "Bouteille..."
                    info = produits_info[nom_tech]
                    x1, y1, x2, y2 = box
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(frame, f"{info['nom']} (ID:{id_objet})", (x1, y1 - 10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    # --- LOGIQUE DE PAIEMENT UNIQUE ---
    ids_vus_precedemment = set(memoire_objets.keys())
    objets_partis = ids_vus_precedemment - objets_actuels_visibles
    
    for id_parti in objets_partis:
        nom_tech_parti = memoire_objets[id_parti]
        info_produit = produits_info[nom_tech_parti]
        
        prix = info_produit["prix"]
        nom_reel = info_produit["nom"]
        
        # Débit du compte
        if solde_client >= prix:
            solde_client -= prix
            panier_total += prix
            print(f"💰 PAIEMENT VALIDÉ : {nom_reel} (ID {id_parti}) -> -{prix} FCFA")
        else:
            print(f"⚠️ SOLDE INSUFFISANT pour la {nom_reel}")
        
        # On supprime de la mémoire pour ne pas facturer plusieurs fois
        del memoire_objets[id_parti]

    # --- INTERFACE VISUELLE (HUD) ---
    # Rectangle bleu pour le solde
    cv2.rectangle(frame, (0, 0), (640, 60), (200, 0, 0), -1)
    affichage = f"SOLDE: {solde_client} F | DERNIER ACHAT: {panier_total} F"
    cv2.putText(frame, affichage, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    cv2.imshow("PICK & GO - SYSTEME BOUTEILLE", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()