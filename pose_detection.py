"""
PoseGuard pose-detection model loader and inference.

Rebuilds the MobileNetV2 architecture and loads weights from the legacy .h5
file (saved with Keras 3) using by_name=True for cross-version compatibility.
"""

import logging
import os
import threading
import time

import numpy as np

logger = logging.getLogger('poseguard.model')

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
_load_lock = threading.Lock()
_load_thread = None

_status = {
    'state': 'idle',       # idle | loading | ready | error
    'progress': 0,
    'message': 'Model not loaded',
    'error': None,
}


def get_model_status():
    with _load_lock:
        return dict(_status)


def _set_status(state, progress, message, error=None):
    with _load_lock:
        _status.update({
            'state': state,
            'progress': progress,
            'message': message,
            'error': error,
        })
    logger.info('[PoseGuard] Model %s (%s%%): %s', state, progress, message)
    if error:
        logger.error('[PoseGuard] Model error: %s', error)


def _build_architecture():
    from tensorflow.keras.applications import MobileNetV2
    from tensorflow.keras import layers, Model

    base = MobileNetV2(input_shape=(224, 224, 3), include_top=False, weights=None)
    x = layers.GlobalAveragePooling2D(name='global_average_pooling2d_1')(base.output)
    x = layers.BatchNormalization(name='batch_normalization_2')(x)
    x = layers.Dense(256, activation='relu', name='dense_3')(x)
    x = layers.Dropout(0.5, name='dropout_2')(x)
    x = layers.BatchNormalization(name='batch_normalization_3')(x)
    x = layers.Dense(128, activation='relu', name='dense_4')(x)
    x = layers.Dropout(0.5, name='dropout_3')(x)
    outputs = layers.Dense(8, activation='softmax', name='dense_5')(x)
    return Model(inputs=base.input, outputs=outputs)


def _load_model_sync():
    """Load the model synchronously. Returns the model or None on failure."""
    global model

    with _load_lock:
        if model is not None:
            return model
        if _status['state'] == 'loading':
            return None
        _status['state'] = 'loading'

    _set_status('loading', 5, 'Initializing model loader…')

    if not os.path.isfile(MODEL_PATH):
        msg = f'Model file not found at {MODEL_PATH}'
        _set_status('error', 0, msg, msg)
        return None

    file_size_mb = os.path.getsize(MODEL_PATH) / (1024 * 1024)
    _set_status('loading', 10, f'Found model file ({file_size_mb:.1f} MB)')

    try:
        _set_status('loading', 20, 'Loading TensorFlow…')
        import tensorflow as tf

        gpus = tf.config.list_physical_devices('GPU')
        if gpus:
            logger.info('[PoseGuard] GPU devices found: %s', [g.name for g in gpus])
            for gpu in gpus:
                try:
                    tf.config.experimental.set_memory_growth(gpu, True)
                except Exception as gpu_err:
                    logger.warning('[PoseGuard] GPU memory growth setup failed: %s', gpu_err)
        else:
            logger.info('[PoseGuard] No GPU detected — using CPU inference')

        _set_status('loading', 40, 'Building model architecture…')
        loaded_model = _build_architecture()

        _set_status('loading', 65, 'Loading trained weights…')
        loaded_model.load_weights(MODEL_PATH, by_name=True)

        _set_status('loading', 85, 'Running warmup inference…')
        dummy = np.zeros((1, 224, 224, 3), dtype=np.float32)
        loaded_model.predict(dummy, verbose=0)

        with _load_lock:
            model = loaded_model

        _set_status('ready', 100, 'Model ready for inference')
        logger.info('[PoseGuard] Model loaded successfully from %s', MODEL_PATH)
        return model

    except Exception as e:
        msg = str(e)
        _set_status('error', _status['progress'], f'Failed to load model: {msg}', msg)
        return None


def preload_model():
    """Start loading the model in a background thread (safe to call multiple times)."""
    global _load_thread

    with _load_lock:
        if model is not None or _status['state'] == 'loading':
            return
        if _load_thread is not None and _load_thread.is_alive():
            return

    def _run():
        _load_model_sync()

    _load_thread = threading.Thread(target=_run, daemon=True, name='model-preload')
    _load_thread.start()


def ensure_model_loaded(timeout=120):
    """Block until the model is loaded or timeout. Returns True if ready."""
    if model is not None:
        return True

    preload_model()

    deadline = time.time() + timeout
    while time.time() < deadline:
        status = get_model_status()
        if status['state'] == 'ready' and model is not None:
            return True
        if status['state'] == 'error':
            return False
        time.sleep(0.25)

    return model is not None


def preprocess_frame(frame):
    import cv2
    resized = cv2.resize(frame, (224, 224))
    normalized = resized.astype('float32') / 255.0
    return np.expand_dims(normalized, axis=0)


def detect_pose(frame):
    if model is None:
        if not ensure_model_loaded(timeout=0.1):
            preload_model()
            status = get_model_status()
            if status['state'] == 'error':
                return (False, status['message'], 0.0)
            return (False, 'Loading model…', 0.0)

    try:
        processed = preprocess_frame(frame)
        predictions = model.predict(processed, verbose=0)
        class_index = int(np.argmax(predictions[0]))
        confidence = float(predictions[0][class_index])
        class_name = CLASS_LABELS[class_index]
        is_unwanted = (class_name != "Normal Pose") and (confidence >= 0.7)
        return (is_unwanted, class_name, confidence)
    except Exception as e:
        logger.exception('[PoseGuard] detect_pose error: %s', e)
        return (False, "Inference Error", 0.0)
