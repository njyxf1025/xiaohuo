# Avatar (数字人) Module

This directory contains bundled **preset avatars** used by the `Singing Digital Human`
backend when no human-curated preset assets are available.

## Layout

- `presets/` – statically bundled preset avatars. The backend auto-generates 3
  placeholder PNGs here on first call to `GET /api/v1/avatars/presets` if the
  directory is empty or `manifest.json` is missing. The manifest is persisted
  so subsequent calls reuse the same assets.
- `presets/manifest.json` – JSON manifest describing each preset. Auto-generated.

> User-uploaded avatars and thumbnails live under the data root resolved by
> `Settings.data_dir` (default `../data/avatars/`, i.e. `<repo>/data/avatars/`).
> They are NOT stored here.

## Preset Generation

When the manifest is missing, the backend draws 3 solid-colour PNGs with a
simple "face" placeholder (round head, eyes, smile arc, label) using Pillow:

| preset_id   | name       | background (RGB) |
| ----------- | ---------- | ----------------- |
| `preset_01` | Preset 01  | (64, 128, 200)    |
| `preset_02` | Preset 02  | (200, 96, 96)     |
| `preset_03` | Preset 03  | (96, 180, 120)    |

Each preset produces a 512×512 PNG file and a 256×256 JPEG thumbnail:

- `presets/preset_NN.png`     – the actual avatar image
- `presets/preset_NN_thumb.jpg` – a small thumbnail used by the gallery UI

To add a real human-curated preset:

1. Drop the image file into `presets/` (e.g. `preset_04.png`).
2. Edit `presets/manifest.json` and add a matching entry:
   ```json
   {
     "preset_id": "preset_04",
     "name": "Avatar Name",
     "filename": "preset_04.png",
     "file_path": "/abs/path/to/presets/preset_04.png",
     "thumbnail_path": "/abs/path/to/presets/preset_04_thumb.jpg",
     "description": "optional human-readable description",
     "created_at": 1700000000.0
   }
   ```
3. Restart the backend (or simply call `GET /api/v1/avatars/presets` again –
   the loader is idempotent and reuses existing entries).

## Bundling Face Detection Models

The face detector (`backend/services/face_detect.py`) looks for an S3FD-style
ONNX model (or a Caffe deploy+weights pair) in the following locations and
falls back to OpenCV's Haar cascade if none is present:

- `backend/models/face_detector/s3fd.onnx`
- `backend/models/face_detector/deploy.prototxt`
  + `res10_300x300_ssd_iter_140000.caffemodel`
- `backend/models/wav2lip/face_detection.onnx`
- `<DATA_DIR>/avatars/models/...`

If no detector is available the upload endpoint gracefully accepts media with
`has_face = null` (verification skipped) and logs a warning at startup.
