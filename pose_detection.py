"""
Loads the Keras model on first use.
Exposes detect_pose(frame) -> (is_unwanted: bool, class_name: str, confidence: float)
"""

import os
import numpy as np

CLASS_LABELS = [
    "Normal Pose",
    "Phone (Using)",
    "Phone (Talking)",
    "Distracted....",
    "Drinking",
    "No Hands on Wheel",
    "Makeup",
    "Looking Away",
]

MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'model', 'poseguard_model.h5')

model = None
_load_attempted = False


def _load_model():
    global model, _load_attempted
    if _load_attempted:
        return model
    _load_attempted = True
    try:
        import tensorflow as tf
        gpus = tf.config.list_physical_devices('GPU')
        for gpu in gpus:
            tf.config.experimental.set_memory_growth(gpu, True)
        from tensorflow import keras
        model = keras.models.load_model(MODEL_PATH)
        print(f"[PoseGuard] Model loaded from {MODEL_PATH}")
    except Exception as e:
        model = None
        print(f"[PoseGuard] Warning: Could not load model: {e}")
    return model


def preprocess_frame(frame):
    import cv2
    resized = cv2.resize(frame, (224, 224))
    normalized = resized.astype('float32') / 255.0
    expanded = np.expand_dims(normalized, axis=0)
    return expanded


def detect_pose(frame):
    if _load_model() is None:
        return (False, "Model Not Loaded", 0.0)
    try:
        processed = preprocess_frame(frame)
        predictions = model.predict(processed, verbose=0)
        class_index = int(np.argmax(predictions[0]))
        confidence = float(predictions[0][class_index])
        class_name = CLASS_LABELS[class_index]
        is_unwanted = (class_name != "Normal Pose") and (confidence >= 0.7)
        return (is_unwanted, class_name, confidence)
    except Exception as e:
        print(f"[PoseGuard] detect_pose error: {e}")
        return (False, "Error", 0.0)
