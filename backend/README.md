# Singing Digital Human - Backend

FastAPI backend for the **Singing Digital Human** web app. The backend owns
music upload + chorus detection, avatar management, and the Wav2Lip-ONNX
inference pipeline that lip-syncs the user-supplied audio onto a digital human
avatar. Wav2Lip-ONNX is the only inference path; ONNX Runtime + DirectML
covers AMD/NVIDIA/Intel GPUs and falls back to CPU when no GPU / driver is
available.

---

## Features

- FastAPI app factory (`create_app()`) wiring system, music, avatar, and
  generation routers under `/api/v1`.
- Structured JSON logging with per-request `request_id` (see
  [Logging](#logging)).
- GPU abstraction layer (`core/gpu.py`) and ONNX provider selection
  (`core/onnx_provider.py`) that prefer DirectML on AMD/NVIDIA/Intel and
  fall back to CPU.
- Music upload (mp3/wav/m4a/flac) with automatic chorus detection
  (pychorus → librosa loudest-window fallback), audio slicing, and
  waveform data.
- Avatar management: image/video upload with face detection, plus built-in
  preset avatars.
- Generation pipeline that runs Wav2Lip-ONNX with progress + status APIs and
  downloadable MP4 results.
- Global exception handler returning `{error, message, request_id}` JSON.

---

## Project layout

```
backend/
  api/                # FastAPI routers (system, music, avatar, generation)
  core/               # config, logging, request_id, gpu, onnx_provider, cors
  models/             # pydantic schemas
  services/           # business logic (music, avatar, generation, wav2lip, ...)
  utils/              # files, ffmpeg, mel, id generation helpers
  tests/              # pytest smoke tests
  data/               # runtime data (uploads, avatars, outputs) — gitignored
  main.py             # FastAPI app factory
  run.py              # uvicorn entrypoint
  pyproject.toml
  requirements.txt
  .env.example
```

---

## Requirements

- Python **3.10+**
- FFmpeg available on `PATH` (used for audio slicing, video muxing, thumbnail
  extraction). Install with your package manager, e.g. `apt install ffmpeg`,
  `brew install ffmpeg`, or `scoop install ffmpeg`.
- (Optional) ONNX Runtime DirectML — only required for GPU acceleration.
  AMD/NVIDIA/Intel GPUs all use the DirectML provider. Without it the
  pipeline falls back to `CPUExecutionProvider`.

## Install

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

If `pychorus` cannot be installed from PyPI on your platform, the chorus
detector in `services/chorus.py` already falls back to a librosa-based
"loudest window" implementation, so the upload pipeline still works.

## Environment variables

All variables are read by `core/config.py` and have sensible defaults. Copy
`.env.example` to `.env` and tweak as needed.

| Variable              | Default       | Description                                              |
| --------------------- | ------------- | -------------------------------------------------------- |
| `API_HOST`            | `0.0.0.0`     | Bind address for uvicorn.                                |
| `API_PORT`            | `8000`        | Bind port for uvicorn.                                   |
| `LOG_LEVEL`           | `info`        | Python log level (`debug`, `info`, `warning`, `error`).  |
| `DATA_DIR`            | `../data`     | Runtime data root (uploads, avatars, outputs, tasks).   |
| `MODELS_DIR`          | `../models`   | Directory holding the Wav2Lip ONNX weights.              |
| `MAX_UPLOAD_MB`       | `200`         | Max music upload size in MB.                             |
| `CORS_ALLOW_ORIGINS`  | `*`           | Comma-separated list of allowed CORS origins.            |
| `DML_DEVICE_ID`       | `0`           | DirectML device id used by the Wav2Lip engine.          |
| `FAKE_DML_DEVICES`    | _unset_       | Test hook — pretends N DML devices are available.       |

## Run

```bash
python run.py
```

`run.py` calls `uvicorn.run("main:app", host=API_HOST, port=API_PORT, ...)`.
The default URL is `http://localhost:8000`. The OpenAPI docs are exposed at
`/docs` and `/redoc`.

### Docker / production

Any ASGI runner works. Example with gunicorn:

```bash
pip install gunicorn
gunicorn -k uvicorn.workers.UvicornWorker -w 1 -b 0.0.0.0:8000 main:app
```

### Tests

```bash
pip install pytest httpx
pytest -q
```

`tests/test_smoke.py` imports the app, calls `/api/v1/health` and
`/api/v1/system/info` with `fastapi.testclient.TestClient`, and asserts that
the expected music, avatar, and generation routes are mounted.

---

## Endpoint table

All endpoints are mounted under the `/api/v1` prefix.

### System

| Method | Path                  | Description                                                            |
| ------ | --------------------- | ---------------------------------------------------------------------- |
| GET    | `/api/v1/health`      | Liveness probe. Returns `status`, `request_id`, GPU summary, ONNX provider. |
| GET    | `/api/v1/system/info` | Returns detected GPUs and the chosen ONNX provider chain.              |
| GET    | `/`                   | Service banner (name, version, API prefix).                            |

### Music

| Method | Path                                        | Description                                                |
| ------ | ------------------------------------------- | ---------------------------------------------------------- |
| POST   | `/api/v1/music/upload`                      | Upload an audio file (mp3/wav/m4a/flac) and auto-detect chorus. |
| GET    | `/api/v1/music/{music_id}`                  | Fetch music metadata (duration, sample rate, chorus, ...). |
| POST   | `/api/v1/music/{music_id}/detect-chorus`    | Re-run chorus detection for an existing upload.            |
| POST   | `/api/v1/music/{music_id}/slice`            | Slice the audio between `start_sec` / `end_sec`.           |
| GET    | `/api/v1/music/{music_id}/waveform`         | Get downsampled peak data for waveform visualization.      |
| GET    | `/api/v1/music/{music_id}/download`         | Download the original uploaded file.                       |
| GET    | `/api/v1/music/slice/{slice_id}/download`   | Download a previously generated audio slice.               |

### Avatars

| Method | Path                                          | Description                                                |
| ------ | --------------------------------------------- | ---------------------------------------------------------- |
| POST   | `/api/v1/avatars/upload`                      | Upload an image or short video as a custom avatar (face detection required). |
| GET    | `/api/v1/avatars`                             | List custom avatars uploaded by the user.                  |
| GET    | `/api/v1/avatars/presets`                     | List built-in preset avatars.                              |
| GET    | `/api/v1/avatars/{avatar_id}`                 | Fetch avatar metadata.                                     |
| GET    | `/api/v1/avatars/{avatar_id}/thumbnail`       | Download the avatar thumbnail (face crop).                 |
| GET    | `/api/v1/avatars/{avatar_id}/file`            | Download the original avatar file.                         |
| DELETE | `/api/v1/avatars/{avatar_id}`                 | Delete a custom avatar.                                    |
| GET    | `/api/v1/avatars/presets/{preset_id}/thumbnail` | Download a preset avatar thumbnail.                      |
| GET    | `/api/v1/avatars/presets/{preset_id}/file`    | Download a preset avatar file.                             |

### Generation

| Method | Path                                       | Description                                                |
| ------ | ------------------------------------------ | ---------------------------------------------------------- |
| POST   | `/api/v1/generation`                       | Start a Wav2Lip generation task.                           |
| GET    | `/api/v1/generation`                       | List recent generation tasks (newest first).               |
| GET    | `/api/v1/generation/{task_id}`             | Get task status, progress, and result metadata.           |
| DELETE | `/api/v1/generation/{task_id}`             | Cancel a pending/running task.                             |
| GET    | `/api/v1/generation/{task_id}/download`    | Download the resulting MP4 (only when status = `success`). |
| GET    | `/api/v1/generation/{task_id}/thumbnail`   | Download the result thumbnail (first frame JPEG).          |
| GET    | `/api/v1/generation/engine/status`         | Inspect the Wav2Lip-ONNX engine (loaded, providers, errors). |
| POST   | `/api/v1/generation/engine/warmup`         | Force-load the Wav2Lip ONNX session.                       |

### Error envelope

All API errors return JSON shaped like:

```json
{ "error": "music_not_found", "message": "music_id=abc not found", "request_id": "..." }
```

Unhandled exceptions are caught by the global exception handler in
`main.py` and return the same shape with HTTP 500 and
`error = "internal_server_error"`.

---

## Logging

`core/logging.py` configures structured JSON logs and injects a per-request
`request_id` (generated by `core/request_id.py`). The startup hook logs
resolved `api_host`, `api_port`, `log_level`, the GPU summary, and the
selected ONNX provider chain. Per-stage events include `stage` (e.g.
`music.upload`, `generation.create`) and elapsed time.

## Model weights

Drop the Wav2Lip ONNX weights into `../models/wav2lip/` (see
`../models/wav2lip/README.md`). The engine refuses to start a generation
task if the weights cannot be located and the global exception handler
surfaces a 503 `model_not_loaded` response.
