from ultralytics import YOLO
import os

if __name__ == '__main__':
    # 1. Charger le modèle de base (YOLOv8 Nano)
    model = YOLO("yolov8n.pt") 

    # 2. Lancer l'apprentissage sur tes données
    # epochs=50 : l'IA va réviser 50 fois tes images
    model.train(
        data="data.yaml", 
        epochs=50, 
        imgsz=640, 
        batch=16, 
        name="pick_and_go_sn"
    )
    print("Entraînement terminé ! Ton modèle est dans : runs/detect/pick_and_go_sn/weights/best.pt")