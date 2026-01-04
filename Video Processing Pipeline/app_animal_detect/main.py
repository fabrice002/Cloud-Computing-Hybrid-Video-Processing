"""
FastAPI YOLO Animal Detection Project
=====================================
Install dependencies:
pip install fastapi uvicorn python-multipart opencv-python ultralytics
"""

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import cv2
from ultralytics import YOLO
import numpy as np
from pathlib import Path
import shutil
from typing import List, Dict
import json
from datetime import datetime
import tempfile
import base64

app = FastAPI(
    title="YOLO Animal Detection API",
    description="API pour détecter des animaux dans des vidéos avec YOLOv8",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Créer les dossiers nécessaires
UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("outputs")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Charger le modèle YOLO
model = YOLO('yolov8n.pt')

# Classes d'animaux dans COCO dataset (utilisé par YOLOv8)
ANIMAL_CLASSES = {
    15: 'chat', 16: 'chien', 17: 'cheval', 18: 'mouton', 
    19: 'vache', 20: 'éléphant', 21: 'ours', 22: 'zèbre', 
    23: 'girafe', 24: 'sac à dos', 25: 'parapluie'
}


@app.get("/")
async def root():
    """Page d'accueil de l'API"""
    return {
        "message": "API de détection d'animaux avec YOLO",
        "endpoints": {
            "/detect": "POST - Télécharger une vidéo pour détection",
            "/detect/frame": "POST - Détecter sur une seule image",
            "/models": "GET - Liste des modèles disponibles",
            "/animals": "GET - Liste des animaux détectables"
        }
    }


@app.get("/animals")
async def get_animals():
    """Retourne la liste complète des classes détectables"""
    all_classes = {id: name for id, name in model.names.items()}
    return {
        "total_classes": len(all_classes),
        "all_classes": all_classes,
        "animal_focus": ANIMAL_CLASSES
    }


@app.post("/detect")
async def detect_video(
    file: UploadFile = File(...),
    confidence_threshold: float = 0.5,
    save_video: bool = True
):
    """
    Détecte les animaux dans une vidéo uploadée
    
    Args:
        file: Fichier vidéo à analyser
        confidence_threshold: Seuil de confiance minimum (0-1)
        save_video: Sauvegarder la vidéo annotée
    
    Returns:
        JSON avec statistiques et détections par frame
    """
    
    # Vérifier l'extension du fichier
    if not file.filename.endswith(('.mp4', '.avi', '.mov', '.mkv')):
        raise HTTPException(400, "Format vidéo non supporté. Utilisez .mp4, .avi, .mov ou .mkv")
    
    # Sauvegarder la vidéo uploadée
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    input_path = UPLOAD_DIR / f"input_{timestamp}_{file.filename}"
    
    with input_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Traiter la vidéo
    try:
        results = process_video(
            str(input_path), 
            confidence_threshold, 
            save_video,
            timestamp
        )
        
        # Nettoyer le fichier uploadé
        input_path.unlink()
        
        return JSONResponse(content=results)
    
    except Exception as e:
        # Nettoyer en cas d'erreur
        if input_path.exists():
            input_path.unlink()
        raise HTTPException(500, f"Erreur lors du traitement: {str(e)}")


@app.post("/detect/frame")
async def detect_frame(file: UploadFile = File(...), confidence_threshold: float = 0.5):
    """
    Détecte les animaux sur une seule image
    
    Args:
        file: Fichier image (jpg, png)
        confidence_threshold: Seuil de confiance minimum
    
    Returns:
        JSON avec détections et image annotée en base64
    """
    
    if not file.filename.endswith(('.jpg', '.jpeg', '.png', '.bmp')):
        raise HTTPException(400, "Format image non supporté")
    
    # Lire l'image
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    if frame is None:
        raise HTTPException(400, "Impossible de lire l'image")
    
    # Détecter
    results = model(frame, conf=confidence_threshold)
    
    detections = []
    for result in results:
        for box in result.boxes:
            class_id = int(box.cls[0])
            confidence = float(box.conf[0])
            coords = box.xyxy[0].tolist()
            
            detections.append({
                "class_id": class_id,
                "class_name": model.names[class_id],
                "confidence": round(confidence, 3),
                "bbox": coords
            })
    
    # Image annotée
    annotated = results[0].plot()
    _, buffer = cv2.imencode('.jpg', annotated)
    img_base64 = base64.b64encode(buffer).decode('utf-8')
    
    return {
        "detections": detections,
        "total_objects": len(detections),
        "annotated_image": img_base64
    }


def process_video(
    video_path: str, 
    conf_threshold: float, 
    save_output: bool,
    timestamp: str
) -> Dict:
    """Traite la vidéo et extrait les détections"""
    
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        raise ValueError("Impossible d'ouvrir la vidéo")
    
    # Infos vidéo
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # Préparer l'enregistrement de la vidéo annotée
    output_video = None
    output_path = None
    
    if save_output:
        output_path = OUTPUT_DIR / f"output_{timestamp}.mp4"
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        output_video = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
    
    # Statistiques
    frame_detections = []
    animals_count = {}
    frame_idx = 0
    
    while cap.isOpened():
        success, frame = cap.read()
        
        if not success:
            break
        
        # Détection avec tracking
        results = model.track(frame, persist=True, conf=conf_threshold)
        
        frame_data = {
            "frame": frame_idx,
            "timestamp": frame_idx / fps,
            "detections": []
        }
        
        for result in results:
            for box in result.boxes:
                class_id = int(box.cls[0])
                class_name = model.names[class_id]
                confidence = float(box.conf[0])
                
                # Compter les animaux
                animals_count[class_name] = animals_count.get(class_name, 0) + 1
                
                # Track ID si disponible
                track_id = int(box.id[0]) if box.id is not None else None
                
                frame_data["detections"].append({
                    "class_id": class_id,
                    "class_name": class_name,
                    "confidence": round(confidence, 3),
                    "track_id": track_id
                })
        
        if frame_data["detections"]:
            frame_detections.append(frame_data)
        
        # Sauvegarder la frame annotée
        if save_output and output_video:
            annotated = results[0].plot()
            output_video.write(annotated)
        
        frame_idx += 1
    
    cap.release()
    if output_video:
        output_video.release()
    
    # Résultats finaux
    return {
        "video_info": {
            "duration_seconds": total_frames / fps,
            "fps": fps,
            "resolution": f"{width}x{height}",
            "total_frames": total_frames,
            "processed_frames": frame_idx
        },
        "detection_summary": {
            "total_detections": sum(animals_count.values()),
            "unique_classes": len(animals_count),
            "animals_detected": animals_count,
            "frames_with_detections": len(frame_detections)
        },
        "detailed_detections": frame_detections[:100],  # Limiter à 100 frames pour la réponse
        "output_video": str(output_path) if save_output else None
    }


@app.get("/output/{filename}")
async def get_output_video(filename: str):
    """Télécharge une vidéo annotée"""
    file_path = OUTPUT_DIR / filename
    
    if not file_path.exists():
        raise HTTPException(404, "Vidéo non trouvée")
    
    return FileResponse(
        path=file_path,
        media_type="video/mp4",
        filename=filename
    )


@app.delete("/output/{filename}")
async def delete_output(filename: str):
    """Supprime une vidéo traitée"""
    file_path = OUTPUT_DIR / filename
    
    if not file_path.exists():
        raise HTTPException(404, "Fichier non trouvé")
    
    file_path.unlink()
    return {"message": f"Fichier {filename} supprimé"}


@app.get("/health")
async def health_check():
    """Vérifie que l'API et le modèle fonctionnent"""
    return {
        "status": "healthy",
        "model_loaded": model is not None,
        "model_type": "YOLOv8n"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app,  port=8000)