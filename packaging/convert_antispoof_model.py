"""Convert MiniVision Silent-Face anti-spoof models (.pth) to ONNX.

Source models + architecture: https://github.com/minivision-ai/Silent-Face-Anti-Spoofing
(Apache License 2.0). This is a one-time / reference script: it needs PyTorch and a
local clone of that repo. The resulting .onnx files are committed under app/assets/,
so the app and CI never need PyTorch — only onnxruntime at runtime.

Usage:
    python packaging/convert_antispoof_model.py --mv-repo C:\\path\\to\\Silent-Face-Anti-Spoofing
"""
from __future__ import annotations

import argparse
import sys
from collections import OrderedDict
from pathlib import Path

import torch

# (pth filename, model class name, output onnx name) — the two models MiniVision
# ensembles. The crop scale (2.7 / 4.0) is applied at inference, not here.
JOBS = [
    ("2.7_80x80_MiniFASNetV2.pth", "MiniFASNetV2", "antispoof_2_7.onnx"),
    ("4_0_0_80x80_MiniFASNetV1SE.pth", "MiniFASNetV1SE", "antispoof_4_0.onnx"),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mv-repo", required=True, help="path to a Silent-Face-Anti-Spoofing clone")
    args = ap.parse_args()

    repo = Path(args.mv_repo).resolve()
    sys.path.insert(0, str(repo))
    from src.model_lib.MiniFASNet import (  # noqa: E402
        MiniFASNetV1SE,
        MiniFASNetV2,
    )
    from src.utility import get_kernel  # noqa: E402

    classes = {"MiniFASNetV2": MiniFASNetV2, "MiniFASNetV1SE": MiniFASNetV1SE}
    out_dir = Path(__file__).resolve().parent.parent / "app" / "assets"
    out_dir.mkdir(parents=True, exist_ok=True)
    kernel = get_kernel(80, 80)

    for pth_name, cls_name, out_name in JOBS:
        model = classes[cls_name](conv6_kernel=kernel)
        state = torch.load(
            repo / "resources" / "anti_spoof_models" / pth_name, map_location="cpu"
        )
        clean = OrderedDict(
            (k[7:] if k.startswith("module.") else k, v) for k, v in state.items()
        )
        model.load_state_dict(clean)
        model.eval()
        dummy = torch.randn(1, 3, 80, 80)
        out = out_dir / out_name
        torch.onnx.export(
            model, dummy, str(out),
            input_names=["input"], output_names=["output"], opset_version=11,
            dynamo=False,  # legacy TorchScript exporter (no onnxscript dependency)
        )
        print("wrote", out)


if __name__ == "__main__":
    main()
