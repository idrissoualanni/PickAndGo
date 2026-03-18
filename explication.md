# Guide : Matériel et Entraînement pour Pick & Go au Sénégal

Mettre en place un magasin autonome ("Pick & Go") au Sénégal (ou globalement en Afrique de l'Ouest) implique de s'adapter aux réalités locales : coupures de courant, chaleur, connectivité internet parfois instable, et la diversité des produits locaux (biscuits, boissons en sachet, jus locaux comme le Bissap ou le Bouye, etc.).

Voici un guide complet sur le matériel électronique requis et la méthodologie pour entraîner votre IA spécifiquement pour ce contexte.

## Phase 1 : Composants Électroniques Nécessaires (Hardware)

Pour une version de production (au-delà de la webcam de téléphone), voici les éléments physiques à assembler :

### 1. Les Caméras (Les Yeux du Système)
Vous avez besoin de caméras fiables, capables de filmer de haut (pour voir les rayons) et/ou de face (pour voir les chariots/paniers).
*   **Caméras IP PoE (Power over Ethernet) :** *Ex: Hikvision ou Dahua*.
    *   **Pourquoi :** Le PoE permet de faire passer la vidéo ET l'électricité dans un seul câble RJ45. Moins de câbles, plus de robustesse.
    *   **Caractéristiques idéales :** 1080p minimum, 30 FPS minimum, grand angle (pour couvrir plusieurs rayons).

### 2. L'Unité de Traitement IA (Le Cerveau)
Faire tourner YOLOv8 en temps réel sur plusieurs caméras demande beaucoup de puissance de calcul (GPU). Le Cloud (AWS/Google) coûte très cher et nécessite une connexion internet parfaite. Il faut donc du **Edge Computing** (traitement sur place).
*   **L'Idéal : NVIDIA Jetson (Orin Nano ou Xavier NX)**
    *   **Pourquoi :** Ce sont de minuscules ordinateurs conçus spécifiquement pour l'IA. Ils consomment très peu d'énergie (idéal sur onduleur ou panneau solaire) et peuvent analyser plusieurs flux vidéo d'un coup.
*   **L'Alternative (Moins chère au début) : Un PC avec une bonne carte graphique (GPU)**
    *   Un PC de bureau classique avec au minimum une carte NVIDIA RTX 3060 ou 4060.
    *   *Problème au Sénégal :* Consomme beaucoup de courant, chauffe vite, nécessite la clim.

### 3. Réseau et Énergie (Crucial au Sénégal)
*   **Switch PoE Gigabit :** Pour relier toutes vos caméras IP à votre ordinateur central (Jetson ou PC) et les alimenter.
*   **Routeur 4G/5G (ex: Orange/Free) avec puce de secours :** Votre algorithme tourne en local, mais vous avez besoin d'internet (Google Sheets / API) pour la facturation final (la transaction financière).
*   **Onduleur (UPS) Robuste (Indispensable !!) :** Pour protéger le PC/Jetson et les caméras des coupures et micro-coupures de la Senelec.

### 4. Le "Smart Shelf" (Optionnel mais recommandé)
Pour aider l'IA, de nombreux magasins autonomes utilisent des étagères connectées.
*   **Capteurs de poids (Load Cells) sous les étagères :** Couplés à un microcontrôleur (Arduino ou Raspberry Pi Pico).
*   **Pourquoi :** Si la caméra voit une main prendre une "Bouteille Kirène", et que l'étagère signale qu'elle s'est allégée de 500 grammes, vous êtes à 100% sûr de l'achat. Cela réduit les erreurs de l'IA.

---

## Phase 2 : Entraîner le Modèle IA pour le Contexte Sénégalais

Le modèle pré-entraîné de YOLO connaît les "personnes", les "voitures", les "tasses", mais il ne connaît pas une bouteille de *Bissap*, un sachet de *Lait Jaboot*, ou un pot de *Chocopain*. Il faut l'entraîner (Fine-tuning).

### Étape 1 : La Collecte de Données (Le plus important)
Il vous faut des milliers de photos de vos produits locaux. **La qualité de l'IA dépend de la qualité de vos photos.**
*   Achetez les produits réels qui seront dans le magasin.
*   Prenez-les en photo dans **toutes les conditions** :
    *   Sur l'étagère du magasin (éclairage néon).
    *   Tenu dans une main (de face, de profil).
    *   Moitié caché (par une main ou un autre objet - *Occlusion*).
    *   Avec des éclairages différents (lumière du jour, nuit, avec/sans flash).
*   *Astuce : Vous pouvez aussi prendre des vidéos de personnes prenant les objets, puis extraire les images de la vidéo (cela génère des milliers d'images rapidement).*

### Étape 2 : L'Annotation des Données (Labelling)
Il faut "montrer" à l'IA où est l'objet sur chaque photo.
*   Utilisez un outil en ligne comme **Roboflow** ou un outil local comme **LabelImg** / **CVAT**.
*   Sur *chaque* photo, vous devez dessiner des cadres (bounding boxes) autour des produits et les étiqueter (ex: `jus_bissap_500ml`, `lait_cailler_jaboot`, `eau_kirene`).
*   *Viser au minimum 300 à 500 images bien annotées **par produit**.*

### Étape 3 : L'Entraînement du Modèle (Training)
Une fois votre "Dataset" (ensemble de données) annoté prêt.
*   Vous pouvez utiliser **Google Colab (Gratuit / Pro)**. Google vous prête des cartes graphiques puissantes dans le cloud pour faire l'entraînement, ce qui vous évite d'acheter un PC à 1.500.000 FCFA juste pour ça.
*   **Code d'entraînement (YOLOv8) :**
    ```python
    from ultralytics import YOLO

    # Charger le modèle de base
    model = YOLO('yolov8n.pt') 

    # Entraîner sur VOTRE dataset (définis dans un fichier data.yaml)
    results = model.train(data='chemin/vers/votre/data.yaml', epochs=100, imgsz=640)
    ```
*   Cela vous générera un nouveau fichier `best.pt`. C'est **votre** modèle, spécialisé pour les produits sénégalais.

### Étape 4 : L'Amélioration Continue (Active Learning)
Même après l'ouverture, l'IA se trompera.
*   Quand l'IA hésite (ex: score de confiance < 0.60 sur une Bouteille Gazelle), programmez le système pour qu'il sauvegarde automatiquement cette image spécifique.
*   À la fin de la semaine, récupérez ces images difficiles, annotez-les à la main correctement, et *ré-entrainez* votre modèle. Il deviendra imbattable sur les produits locaux.

> **Résumé pour commencer dès maintenant :** 
> N'achetez pas de matériel cher tout de suite. Prenez 5 produits typiques sénégalais chez la boutique du coin, installez une webcam basique en hauteur, prenez une centaine de photos de ces objets manipulés, annotez-les avec Roboflow, et entraînez votre premier petit modèle `produits_locaux.pt` sur Google Colab !
