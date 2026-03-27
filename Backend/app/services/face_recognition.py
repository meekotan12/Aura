"""Use: Contains the main backend rules for face profile, liveness, and recognition rules.
Where to use: Use this from routers, workers, or other services when face profile, liveness, and recognition rules logic is needed.
Role: Service layer. It keeps business logic out of the route files.
"""

from __future__ import annotations

# --- Standard Python libraries ---
import base64
import hashlib
import importlib
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

# --- Third-party libraries ---
import numpy as np
from fastapi import HTTPException, status
from PIL import Image, UnidentifiedImageError

# --- App config ---
from app.core.config import get_settings

# --- Optional libraries ---
try:
    import cv2
except Exception:  # pragma: no cover - optional dependency
    cv2 = None

try:
    import onnxruntime as ort
except Exception:  # pragma: no cover - optional dependency
    ort = None


# ---------------------------------------------
# Dataclasses
# These are simple containers for related data.
# ---------------------------------------------


@dataclass
class LivenessResult:
    """Result of the anti-spoof or liveness check."""

    label: str
    score: float
    reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Convert the result into a JSON-friendly dictionary."""
        payload: dict[str, object] = {
            "label": self.label,
            "score": round(float(self.score), 6),
        }
        if self.reason:
            payload["reason"] = self.reason
        return payload


@dataclass
class FaceCandidate:
    """One known or registered face that can be matched against."""

    identifier: int | str
    label: str
    encoding_bytes: bytes


@dataclass
class FaceMatchResult:
    """Result of comparing a probe face against one reference or many candidates."""

    matched: bool
    threshold: float
    distance: float
    confidence: float
    candidate: FaceCandidate | None = None


@dataclass
class DetectedFaceProbe:
    """One detected face from a probe image, including liveness and encoding state."""

    index: int
    location: tuple[int, int, int, int]
    liveness: LivenessResult
    encoding: np.ndarray | None = None
    error_code: str | None = None


# ---------------------------------------------
# Main service class
# This is where the face logic lives.
# ---------------------------------------------


class FaceRecognitionService:
    def __init__(self) -> None:
        # Load thresholds, model paths, and feature flags from app settings.
        self.settings = get_settings()

        # Anti-spoof model state. These are loaded only when first needed.
        self._anti_spoof_session = None
        self._anti_spoof_input_name: str | None = None
        self._anti_spoof_output_name: str | None = None
        self._anti_spoof_input_size: tuple[int, int] | None = None
        self._anti_spoof_initialized = False

    # ---------------------------------------------
    # Helper: find the anti-spoof model path
    # ---------------------------------------------

    def _default_anti_spoof_model_path(self) -> Path:
        """Return the configured anti-spoof path or the default model path."""
        configured = self.settings.anti_spoof_model_path.strip()
        if configured:
            return Path(configured)
        return Path(__file__).resolve().parents[2] / "models" / "MiniFASNetV2.onnx"

    def face_recognition_status(self) -> tuple[bool, str | None]:
        """Return whether the `face_recognition` runtime is available."""
        try:
            self._require_face_recognition_library()
        except HTTPException:
            return False, "face_recognition_unavailable"
        return True, None

    @staticmethod
    def _require_face_recognition_library() -> Any:
        """Load the optional face-recognition runtime only when a face route needs it."""
        try:
            return importlib.import_module("face_recognition")
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Face recognition runtime is unavailable. "
                    "Install the 'face_recognition' dependency to use face features."
                ),
            ) from exc

    # ---------------------------------------------
    # Static utilities
    # These helpers do not need access to self.
    # ---------------------------------------------

    @staticmethod
    def decode_base64_image(image_base64: str) -> bytes:
        """Decode a base64 image string into raw bytes."""
        if not image_base64 or not image_base64.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Image payload is required.",
            )

        payload = image_base64.strip()
        if "," in payload:
            payload = payload.split(",", 1)[1]

        try:
            return base64.b64decode(payload, validate=True)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Image payload is not valid base64.",
            ) from exc

    @staticmethod
    def load_rgb_from_bytes(image_bytes: bytes) -> np.ndarray:
        """Open raw image bytes and convert them into an RGB NumPy array."""
        try:
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        except (UnidentifiedImageError, OSError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is not a valid image.",
            ) from exc
        return np.array(image)

    @staticmethod
    def compute_image_sha256(image_bytes: bytes) -> str:
        """Return a SHA-256 fingerprint for an image."""
        return hashlib.sha256(image_bytes).hexdigest()

    @staticmethod
    def encoding_to_bytes(encoding: np.ndarray) -> bytes:
        """Convert a face encoding array into raw bytes for storage."""
        normalized = np.asarray(encoding, dtype=np.float64)
        return normalized.tobytes()

    @staticmethod
    def encoding_from_bytes(encoding_bytes: bytes) -> np.ndarray:
        """Convert stored raw bytes back into a face encoding array."""
        if not encoding_bytes:
            raise ValueError("Face encoding bytes are empty.")
        return np.frombuffer(encoding_bytes, dtype=np.float64)

    @staticmethod
    def _softmax(values: np.ndarray) -> np.ndarray:
        """Convert raw model scores into probabilities."""
        exp_values = np.exp(values - np.max(values, axis=1, keepdims=True))
        return exp_values / exp_values.sum(axis=1, keepdims=True)

    @staticmethod
    def _xyxy_to_xywh(x1: int, y1: int, x2: int, y2: int) -> list[int]:
        """Convert a box from corner format into x, y, width, height format."""
        return [int(x1), int(y1), int(x2 - x1), int(y2 - y1)]

    @staticmethod
    def _crop_face_bgr(
        image_bgr: np.ndarray,
        bbox_xywh: list[int],
        scale: float,
        out_h: int,
        out_w: int,
    ) -> np.ndarray:
        """Crop the face and resize it to the exact size the model expects."""
        src_h, src_w = image_bgr.shape[:2]
        x, y, box_w, box_h = bbox_xywh

        # Scale down when needed so the crop stays inside the image.
        scale = min((src_h - 1) / max(box_h, 1), (src_w - 1) / max(box_w, 1), scale)

        new_w = box_w * scale
        new_h = box_h * scale
        center_x = x + box_w / 2
        center_y = y + box_h / 2

        left = max(0, int(center_x - new_w / 2))
        top = max(0, int(center_y - new_h / 2))
        right = min(src_w - 1, int(center_x + new_w / 2))
        bottom = min(src_h - 1, int(center_y + new_h / 2))

        cropped = image_bgr[top : bottom + 1, left : right + 1]
        if cropped.size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid face crop for liveness detection.",
            )
        if cv2 is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="opencv-python-headless is required for liveness detection.",
            )
        return cv2.resize(cropped, (out_w, out_h))

    # ---------------------------------------------
    # Anti-spoof and liveness detection
    # ---------------------------------------------

    def _init_anti_spoof(self) -> None:
        """Load the anti-spoof ONNX model once, the first time it is needed."""
        if self._anti_spoof_initialized:
            return

        self._anti_spoof_initialized = True
        model_path = self._default_anti_spoof_model_path()

        if ort is None or cv2 is None or not model_path.exists():
            return

        providers = ["CPUExecutionProvider"]
        try:
            available = set(ort.get_available_providers())
            if "CUDAExecutionProvider" in available:
                providers.insert(0, "CUDAExecutionProvider")
        except Exception:
            pass

        session = ort.InferenceSession(str(model_path), providers=providers)
        input_meta = session.get_inputs()[0]
        output_meta = session.get_outputs()[0]
        height = int(input_meta.shape[2])
        width = int(input_meta.shape[3])

        self._anti_spoof_session = session
        self._anti_spoof_input_name = input_meta.name
        self._anti_spoof_output_name = output_meta.name
        self._anti_spoof_input_size = (height, width)

    def anti_spoof_status(self) -> tuple[bool, str | None]:
        """Return whether the anti-spoof model is ready, plus a reason if not."""
        self._init_anti_spoof()
        if self._anti_spoof_session is not None:
            return True, None

        model_path = self._default_anti_spoof_model_path()
        if ort is None:
            return False, "onnxruntime_unavailable"
        if cv2 is None:
            return False, "opencv_unavailable"
        if not model_path.exists():
            return False, "model_missing"
        return False, "session_unavailable"

    def liveness_passed(self, result: LivenessResult) -> bool:
        """Decide if a liveness result counts as passed."""
        if result.label == "Bypassed":
            return True
        return result.label == "Real" and float(result.score) >= self.settings.liveness_min_score

    def check_liveness(self, rgb_image: np.ndarray) -> LivenessResult:
        """Run the anti-spoof check and return whether the face is real or fake."""
        face_recognition_module = self._require_face_recognition_library()
        ready, reason = self.anti_spoof_status()
        if not ready:
            if self.settings.allow_liveness_bypass_when_model_missing:
                return LivenessResult(
                    label="Bypassed",
                    score=1.0,
                    reason=reason or "model_unavailable",
                )

            detail = "Liveness model is not available."
            if reason:
                detail = f"Liveness model is not available ({reason})."
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=detail,
            )

        face_locations = face_recognition_module.face_locations(rgb_image)
        if not face_locations:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No face detected for liveness verification.",
            )
        if len(face_locations) != 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Upload an image with exactly one face for liveness verification.",
            )

        return self._check_liveness_for_location(rgb_image, face_locations[0])

    def _check_liveness_for_location(
        self,
        rgb_image: np.ndarray,
        face_location: tuple[int, int, int, int],
    ) -> LivenessResult:
        """Run anti-spoof against a specific detected face location."""
        ready, reason = self.anti_spoof_status()
        if not ready:
            if self.settings.allow_liveness_bypass_when_model_missing:
                return LivenessResult(
                    label="Bypassed",
                    score=1.0,
                    reason=reason or "model_unavailable",
                )

            detail = "Liveness model is not available."
            if reason:
                detail = f"Liveness model is not available ({reason})."
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=detail,
            )

        top, right, bottom, left = face_location
        bbox_xywh = self._xyxy_to_xywh(left, top, right, bottom)
        image_bgr = rgb_image[:, :, ::-1].copy()
        input_height, input_width = self._anti_spoof_input_size or (80, 80)
        face_crop = self._crop_face_bgr(
            image_bgr,
            bbox_xywh,
            self.settings.anti_spoof_scale,
            input_height,
            input_width,
        )

        # The ONNX model expects a batch in channel-first format.
        model_input = face_crop.astype(np.float32)
        model_input = np.transpose(model_input, (2, 0, 1))
        model_input = np.expand_dims(model_input, axis=0)

        logits = self._anti_spoof_session.run(
            [self._anti_spoof_output_name],
            {self._anti_spoof_input_name: model_input},
        )[0]
        probabilities = self._softmax(logits)
        label_index = int(np.argmax(probabilities))
        score = float(probabilities[0, label_index])
        label = "Real" if label_index == 1 else "Fake"
        return LivenessResult(label=label, score=score)

    # ---------------------------------------------
    # Core face recognition methods
    # ---------------------------------------------

    def extract_encoding_from_bytes(
        self,
        image_bytes: bytes,
        *,
        require_single_face: bool = True,
        enforce_liveness: bool = False,
    ) -> tuple[np.ndarray, LivenessResult]:
        """Load an image, optionally run liveness, then return its face encoding."""
        probes = self.analyze_faces_from_bytes(
            image_bytes,
            enforce_liveness=enforce_liveness,
        )
        if require_single_face and len(probes) != 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Image must contain exactly one face.",
            )

        probe = probes[0]
        if probe.error_code == "spoof_detected":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Spoof detected. label={probe.liveness.label} score={probe.liveness.score:.3f}",
            )
        if probe.encoding is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to compute a face encoding from the image.",
            )

        return np.asarray(probe.encoding, dtype=np.float64), probe.liveness

    def analyze_faces_from_bytes(
        self,
        image_bytes: bytes,
        *,
        enforce_liveness: bool = False,
        max_faces: int | None = None,
    ) -> list[DetectedFaceProbe]:
        """Detect all faces in a probe image and return per-face liveness and encodings."""
        face_recognition_module = self._require_face_recognition_library()
        rgb_image = self.load_rgb_from_bytes(image_bytes)
        face_locations = face_recognition_module.face_locations(rgb_image)
        if not face_locations:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No face detected in image.",
            )

        if max_faces is not None and len(face_locations) > max_faces:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Too many faces detected in one frame. Maximum allowed is {max_faces}.",
            )

        encodings = face_recognition_module.face_encodings(
            rgb_image,
            known_face_locations=face_locations,
        )
        if len(encodings) != len(face_locations):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to compute encodings for all detected faces.",
            )

        probes: list[DetectedFaceProbe] = []
        for index, location in enumerate(face_locations):
            if enforce_liveness:
                liveness = self._check_liveness_for_location(rgb_image, location)
            else:
                liveness = LivenessResult(
                    label="Bypassed",
                    score=1.0,
                    reason="not_requested",
                )

            error_code = None
            encoding = np.asarray(encodings[index], dtype=np.float64)
            if enforce_liveness and not self.liveness_passed(liveness):
                error_code = "spoof_detected"
                encoding = None

            probes.append(
                DetectedFaceProbe(
                    index=index,
                    location=location,
                    liveness=liveness,
                    encoding=encoding,
                    error_code=error_code,
                )
            )

        return probes

    def compare_encodings(
        self,
        probe_encoding: np.ndarray,
        reference_encoding: np.ndarray,
        *,
        threshold: float | None = None,
    ) -> FaceMatchResult:
        """Compare two face encodings and return a structured match result."""
        distance = float(np.linalg.norm(probe_encoding - reference_encoding))
        effective_threshold = float(
            self.settings.face_match_threshold if threshold is None else threshold
        )
        confidence = max(0.0, 1.0 - distance)

        return FaceMatchResult(
            matched=distance <= effective_threshold,
            threshold=effective_threshold,
            distance=distance,
            confidence=confidence,
        )

    def find_best_match(
        self,
        probe_encoding: np.ndarray,
        candidates: Iterable[FaceCandidate],
        *,
        threshold: float | None = None,
    ) -> FaceMatchResult:
        """Compare a probe face against many candidates and return the closest match."""
        best_candidate: FaceCandidate | None = None
        best_distance = float("inf")

        for candidate in candidates:
            reference_encoding = self.encoding_from_bytes(candidate.encoding_bytes)
            distance = float(np.linalg.norm(probe_encoding - reference_encoding))
            if distance < best_distance:
                best_distance = distance
                best_candidate = candidate

        effective_threshold = float(
            self.settings.face_match_threshold if threshold is None else threshold
        )
        if best_candidate is None:
            return FaceMatchResult(
                matched=False,
                threshold=effective_threshold,
                distance=float("inf"),
                confidence=0.0,
                candidate=None,
            )

        return FaceMatchResult(
            matched=best_distance <= effective_threshold,
            threshold=effective_threshold,
            distance=best_distance,
            confidence=max(0.0, 1.0 - best_distance),
            candidate=best_candidate,
        )


def is_face_scan_bypass_enabled_for_email(email: str | None) -> bool:
    if not email:
        return False
    settings = get_settings()
    normalized_email = email.strip().lower()
    return normalized_email in set(settings.face_scan_bypass_emails)


def is_face_scan_bypass_enabled_for_user(user: Any) -> bool:
    return is_face_scan_bypass_enabled_for_email(getattr(user, "email", None))
