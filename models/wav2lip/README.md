# Wav2Lip-ONNX model weights

This directory holds the Wav2Lip ONNX exports consumed by the backend
inference pipeline. The backend looks for the following filenames (the
constants in `core/wav2lip.py` will match these once the model wrapper is
added in Task 5):

- `wav2lip.onnx`            — main Wav2Lip generator (mel -> lip-synced face)
- `face_detection.onnx`     — S3FD face detector (preferred; replaces s3fd.onnx)
- `s3fd.onnx`               — alternative filename accepted for the face detector

## Acquisition

The ONNX exports are not bundled with this repository. To obtain them:

1. Clone the upstream Wav2Lip repo (or use a community ONNX export).
2. Export / download the two `.onnx` files listed above.
3. Drop them into this directory with the exact filenames shown.

The backend treats missing files as a soft failure: the `/api/v1/health`
endpoint will keep returning `200 OK`, but any video generation call will
fail with a clear "model weights not found" error pointing to this path.

## File size sanity check

- `wav2lip.onnx` is typically ~140 MB.
- `face_detection.onnx` / `s3fd.onnx` is typically ~30 MB.

If your files are dramatically smaller, the export is likely incomplete.
