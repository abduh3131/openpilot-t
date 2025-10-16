import pathlib

import pytest

np = pytest.importorskip('numpy')

from scootpilot_perception.onnx_rt import OnnxRunner, load_inputs

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_load_inputs_shape():
    image = np.zeros((240, 320, 3), dtype=np.uint8)
    inputs = load_inputs(image)
    assert list(inputs['input'].shape) == [1, 3, 240, 320]


def test_fake_session_mask_shape():
    model_path = ROOT / 'models' / 'drivable_seg.onnx'
    runner = OnnxRunner(str(model_path))
    image = np.zeros((240, 320, 3), dtype=np.uint8)
    inputs = load_inputs(image)
    result = runner.infer(inputs)
    output = next(iter(result.outputs.values()))
    assert output.shape[-2:] == (240, 320)
