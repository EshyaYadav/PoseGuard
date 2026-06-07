import cv2
import numpy as np
from tensorflow.keras.models import load_model
import os
import tensorflow as tf

# Enable GPU memory growth to prevent TF from taking all GPU memory
physical_devices = tf.config.list_physical_devices('GPU')
if physical_devices:
    try:
        for device in physical_devices:
            tf.config.experimental.set_memory_growth(device, True)
    except RuntimeError as e:
        print(e)

# Ensure model path is correct using absolute path
current_dir = os.path.dirname(os.path.abspath(__file__))
model_path = os.path.join(current_dir, 'model', 'poseguard_model.h5')

# Load model only once when module is imported
try:
    model = load_model(model_path)
except Exception as e:
    print(f"Error loading model: {e}")
    raise

# Standardized class labels
class_labels = [
    "Normal Pose",       # class 0
    "Phone (Using)",      # class 1
    "Phone (Talking)",       # class 2
    "Distracted....",           # class 3
    "Drinking",      # class 4
    "No Hands on Wheel", # class 5
    "Makeup",          # class 6
    "Looking Away"  # class 7
]

# Define unwanted classes (all except Normal Pose)
unwanted_classes = [label for label in class_labels if label != "Normal Pose"]

def preprocess_frame(frame):
    # Skip BGR conversion if already in BGR format
    if len(frame.shape) == 3 and frame.shape[2] == 3:
        resized = cv2.resize(frame, (224, 224))
    else:
        resized = cv2.resize(frame, (224, 224))
    # Normalize to [0,1] range
    norm = resized.astype('float32') / 255.0
    return np.expand_dims(norm, axis=0)

def detect_pose(frame):
    try:
        img = preprocess_frame(frame)
        prediction = model.predict(img, verbose=0)
        pred_class = np.argmax(prediction[0])
        class_name = class_labels[pred_class]
        confidence = float(prediction[0][pred_class])

        is_unwanted = class_name in unwanted_classes and confidence > 0.7
        return is_unwanted, class_name, confidence
    except Exception as e:
        print(f"Error in detect_pose: {e}")
        return False, "Error", 0.0
