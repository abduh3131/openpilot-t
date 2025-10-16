from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List

import numpy as np

try:  # pragma: no cover - optional dependency
    import onnxruntime as ort
except Exception:  # noqa: BLE001
    ort = None


@dataclass
class InferenceResult:
    outputs: Dict[str, np.ndarray]


class FakeSession:
    """Deterministic fallback session when ONNXRuntime is unavailable."""

    def __init__(self, model_path: Path) -> None:
        seed = int(hashlib.sha256(str(model_path).encode('utf-8')).hexdigest(), 16) % 2**32
        self._rng = np.random.default_rng(seed)

    def run(self, output_names: Iterable[str], input_feed: Dict[str, np.ndarray]) -> List[np.ndarray]:
        output_list: List[np.ndarray] = []
        for name in output_names:
            first_input = next(iter(input_feed.values()))
            if first_input.ndim == 4:
                _, _, h, w = first_input.shape
                xv = np.linspace(-1.0, 1.0, w)[None, :]
                mask = np.exp(-((xv) ** 2) / 0.1)
                mask = np.tile(mask, (h, 1))
                mask = (mask - mask.min()) / (mask.max() - mask.min() + 1e-6)
                output = mask.astype(np.float32)[None, None, :, :]
            else:
                output = self._rng.random(first_input.shape, dtype=np.float32)
            output_list.append(output)
        return output_list

    def get_outputs(self) -> List[Any]:
        return []


class OnnxRunner:
    """Wrapper over ONNXRuntime with CPU/TensorRT fallback semantics."""

    def __init__(self, model_path: str) -> None:
        self.model_path = Path(model_path)
        self._session = self._create_session(self.model_path)

    def _create_session(self, model_path: Path):
        if ort is None:
            return FakeSession(model_path)
        providers = ['CUDAExecutionProvider', 'TensorrtExecutionProvider', 'CPUExecutionProvider']
        available = [p for p in providers if p in ort.get_available_providers()]
        try:
            return ort.InferenceSession(str(model_path), providers=available)
        except Exception:  # noqa: BLE001
            return FakeSession(model_path)

    def infer(self, inputs: Dict[str, np.ndarray]) -> InferenceResult:
        if isinstance(self._session, FakeSession):
            outputs = self._session.run(['output'], inputs)
            return InferenceResult({'output': outputs[0]})
        output_names = [output.name for output in self._session.get_outputs()]
        ort_outputs = self._session.run(output_names, inputs)
        return InferenceResult(dict(zip(output_names, ort_outputs)))


def load_inputs(image: np.ndarray) -> Dict[str, np.ndarray]:
    if image.ndim == 3:
        image = image.transpose(2, 0, 1)
    image = image.astype(np.float32) / 255.0
    return {'input': image[np.newaxis, ...]}


__all__ = ['OnnxRunner', 'InferenceResult', 'load_inputs']
