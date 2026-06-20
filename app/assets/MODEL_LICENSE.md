# Passive anti-spoof models — attribution

`antispoof_2_7.onnx` and `antispoof_4_0.onnx` are ONNX conversions of the
**Silent-Face-Anti-Spoofing** models by MiniVision:

- Source: https://github.com/minivision-ai/Silent-Face-Anti-Spoofing
- License: **Apache License 2.0**
- Original files: `2.7_80x80_MiniFASNetV2.pth`, `4_0_0_80x80_MiniFASNetV1SE.pth`

They were converted from PyTorch to ONNX with
[`packaging/convert_antispoof_model.py`](../../packaging/convert_antispoof_model.py);
the model weights and architecture are unchanged. The Apache 2.0 license applies to
these model files. See https://www.apache.org/licenses/LICENSE-2.0 for the full text.
