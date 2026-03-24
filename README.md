# Pick & Go — Smart Store

Systeme de caisse autonome par vision par ordinateur.
Le client prend un produit devant la camera, il est detecte automatiquement et debite de son compte.

> Dataset : Roboflow + Bing Images | Base de donnees : Google Sheets via Apps Script

## Architecture

```
Webcam  -->  YOLOv8 (detect.py)  -->  API Google Sheets  -->  Dashboard (app.py)
```

## Produits detectes (8 classes)

| Classe         | Produit         | Prix (FCFA) |
|----------------|-----------------|-------------|
| Bouteille_Eau  | Bouteille d'Eau | 300         |
| Cahier         | Cahier          | 500         |
| Stylo          | Stylo           | 200         |
| Gazelle        | Biere Gazelle   | 800         |
| Choco_Pain     | Choco Pain      | 250         |
| Bissap         | Jus Bissap      | 400         |
| Riz            | Sac de Riz      | 1500        |
| Huile          | Huile           | 2000        |

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

```bash
cp .env.example .env
# Editer .env et renseigner URL_API (Google Apps Script)
```

## Utilisation

### 1. Tester le modele sur une image
```bash
python test_model.py                         # utilise 624440.webp par defaut
python test_model.py chemin/vers/photo.jpg   # image personnalisee
```

### 2. Detection en temps reel (webcam)
```bash
python detect.py               # webcam index 0
python detect.py --camera 1    # autre webcam
python detect.py --image photo.jpg  # image fixe
```

### 3. Dashboard client
```bash
streamlit run app.py
```

### 4. Entrainer un nouveau modele (Google Colab GPU T4)
Ouvrir `train_colab.ipynb` sur [Google Colab](https://colab.research.google.com).

## Structure

```
PickAndGo/
  detect.py           # Detection temps reel (point d'entree principal)
  test_model.py       # Test rapide sur image
  app.py              # Dashboard Streamlit client
  config.py           # Catalogue produits + parametres
  train_colab.ipynb   # Notebook entrainement GPU
  requirements.txt
  .env.example
  models/
    pick_and_go/
      weights/
        best.pt       # Modele entraine (telecharger depuis Colab)
```

## Modele YOLOv8

- Architecture : YOLOv8n (nano, leger et rapide)
- Dataset : 80 images/classe, split 80/20 train/val
- Entrainement : Google Colab GPU T4, 50 epochs, patience 10

## Base de donnees

Google Sheets via Google Apps Script.
Chaque achat envoie un POST avec `{userID, produit, montant, action}`.
Le script retourne `{status, nouveau_solde, message}`.
