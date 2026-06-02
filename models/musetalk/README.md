# MuseTalk model weights (step-2 deliverable)

This directory is reserved for the MuseTalk weights that the backend will
load through the PyTorch + `torch-directml` provider when step 2 of the
rollout lands. The backend is wired today — the route `POST
/api/v1/generation/musetalk`, the engine singleton in
`services/musetalk_engine.py`, the strict DirectML probe, and weight
discovery are all in place — but the actual inference graph is the
step-2 deliverable. Until the graph lands, requests to
`/api/v1/generation/musetalk` fail with `code="not_implemented"` and
the frontend should keep `selectedModel="wav2lip"` as the default.

## Files the engine will look for

The discovery routine in `services/musetalk_engine.py` (function
`_discover_paths`) walks this directory and the `MUSETALK_DIR` env var
and accepts any of the following filenames for the main model:

- `musetalk.safetensors`
- `musetalk.onnx`
- `musetalk.pt`
- `musetalk.pth`
- `MuseTalk.safetensors`
- `MuseTalk.pt`
- `musetalk_fp16.safetensors`
- `musetalk_fp32.safetensors`

The engine will additionally look for these auxiliaries (optional but
recommended for higher quality):

- `config.yaml` or `musetalk.json` — inference config / VAE / UNet
  hyperparameters
- `hubert.pt` / `chinese-hubert.pt` / `hubert_base.pt` — HuBERT audio
  feature extractor used to feed the lip-sync UNet

## Acquisition

The MuseTalk weights are not bundled with this repository. To obtain
them:

1. Clone the upstream MuseTalk repository (e.g. `TMElyralab/MuseTalk`).
2. Follow their download script to fetch the trained UNet + VAE +
   HuBERT checkpoints.
3. Drop the files into this directory (or set `MUSETALK_DIR` to a
   custom path before starting the backend).

## Hardware expectations

- The PyTorch + DirectML provider path requires a DirectML-capable
  GPU; on Windows the AMD 6700 XT is the primary target. CPU fallback
  is intentionally disabled — the same strict-DirectML policy that
  protects the Wav2Lip engine applies here.
- MuseTalk inference is meaningfully slower than Wav2Lip-ONNX. The
  frontend should make this tradeoff explicit (see the
  `ModelSelector` component) and only route to MuseTalk when the user
  has selected the high-quality path.

## File size sanity check

- `musetalk.safetensors` is typically 1–4 GB depending on the variant.
- `hubert.pt` is typically ~360 MB.

If your files are dramatically smaller, the download is likely
incomplete.
