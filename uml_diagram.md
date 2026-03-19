# Architecture UML - Pick & Go

Ce document présente l'architecture technique du projet via des diagrammes Mermaid.

## 1. Diagramme de Classe (Structure du Système)

```mermaid
classDiagram
    class CameraFeed {
        +String stream_url
        +cv2.VideoCapture cap
        +update()
        +read() Frame
    }

    class SmartStore {
        +YOLO model_pers
        +YOLO model_prod
        +Dict products
        +Set paid_ids
        +process_frame(frame)
        +send_payment(item, price, uid)
    }

    class YOLO_Model {
        <<service>>
        +predict(frame)
        +track(frame)
    }

    class GoogleAppsScript_API {
        <<service>>
        +doPost(e) JSON
        +doGet(e) JSON
        +updateSheet()
    }

    class Google_Sheets {
        <<database>>
        +Table Utilisateurs
        +Table Transactions
    }

    class Streamlit_Dashboard {
        <<frontend>>
        +wallet_section()
        +manual_simulation()
    }

    SmartStore "1" *-- "1" CameraFeed : utilise
    SmartStore "1" o-- "2" YOLO_Model : utilise (Pers/Prod)
    SmartStore ..> GoogleAppsScript_API : envoie POST
    Streamlit_Dashboard ..> GoogleAppsScript_API : envoie POST/GET
    GoogleAppsScript_API -- Google_Sheets : lit/écrit
```

## 2. Diagramme de Séquence (Flux d'Achat Pick & Go)

```mermaid
sequenceDiagram
    participant Cam as Caméra (Téléphone)
    participant AI as IA (main_spatial.py)
    participant API as API (Google Apps Script)
    participant DB as Google Sheets
    participant UI as Dashboard (Streamlit)

    Cam->>AI: Envoi du flux vidéo (Frame)
    AI->>AI: Détection Personne + Produit
    Note over AI: L'utilisateur prend une bouteille
    AI->>AI: Détection disparition (Logique Spatiale)
    AI->>API: POST /exec (userID, produit, montant)
    activate API
    API->>DB: Vérifier solde + Retirer montant
    API->>DB: Ajouter ligne Transaction
    DB-->>API: Confirmation
    API-->>AI: Réponse JSON (nouveau_solde)
    deactivate API
    AI->>AI: Affiche "ACHAT VALIDE" sur la vidéo

    loop Toutes les 10 secondes
        UI->>API: GET /exec (Refresh data)
        API->>DB: Lire historique
        DB-->>API: Données
        API-->>UI: JSON Transactions
        UI->>UI: Mise à jour affichage solde/historique
    end
```

## 3. Description des Composants

*   **main_spatial.py** : Le cerveau du projet. Il gère la vision par ordinateur, le tracking botsort et la logique de proximité entre le client et l'objet.
*   **google_apps_script.js** : Le backend "Serverless" qui sécurise les calculs de solde et gère l'écriture dans le tableur.
*   **app.py** : L'interface utilisateur premium permettant au client de suivre ses dépenses et de simuler des recharges.
*   **.env** : Centralise la connectivité (IP de la caméra et URL du serveur Cloud).
