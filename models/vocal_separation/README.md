# Vocal Separation Models

This directory hosts ONNX vocal-separation / accompaniment-removal models used by
`backend/services/vocal_separation.py` to extract clean vocals from a music
clip **before** feeding the Wav2Lip lip-sync model. Doing this avoids the
"lip jitter caused by heavy-bass accompaniment" problem and gives a much more
stable mouth movement.

The pipeline is:

```
uploaded music
   │
   ├──► slice [chorus_start, chorus_end]
   │
   ├──► vocal_separation.separate(slice)
   │         │
   │         ├──► vocals.wav        ──►  Wav2Lip inference  ──► video
   │         └──► accompaniment.wav  ──►  remux (accompaniment + generated video)
   │
   └──► final.mp4  (lipsync on vocals, but the user hears the full song)
```

## Expected filenames (any one is enough; the service falls back through them)

| Filename                       | Recommended source                                                | Notes                                |
| ------------------------------ | ----------------------------------------------------------------- | ------------------------------------ |
| `vocal_separation.onnx`        | the project's own exported model                                  | preferred; takes 2-stem input/output |
| `mel_band_roformer.onnx`       | UVR5 / Mel-Band-Roformer export (KimberleyJensen, anvuew, etc.)   | 4-stem capable; service picks 2 stems|
| `htdemucs.onnx`                | UVR5 / htdemucs export                                            | good quality, heavier                 |
| `spleeter_2stems.onnx`         | Spleeter 2-stems export                                            | lightweight                          |
| `mdx_q.onnx` / `kim_vocal.onnx`| MDX-Net / Kim Vocal 2 export                                      | also accepted                         |

If **none** of these are present, the service **gracefully falls back** to
using the original sliced audio as the "vocals" track — but logs a clear
warning that no separation model is installed and the user may see lip jitter
on heavy-bass songs. No CPU fallback is ever attempted: the service is
**DirectML only**, exactly like Wav2Lip.

## Soft failure semantics

`vocal_separation.separate()` always returns `(vocals_path, accompaniment_path)`:

- model present + DML ready → both stems are real files
- model missing → vocals_path = original sliced audio, accompaniment_path = None
- model present but DML missing → raises `DirectMLNotAvailable`, the pipeline
  marks the task as `failed` with `error=directml_unavailable`

## Recommended setup (AMD 6700XT)

```bash
# 1. Download a UVR5 Mel-Band-Roformer ONNX export
curl -L -o models/vocal_separation/mel_band_roformer.onnx \
  https://huggingface.co/your-favorite-uvr5-export/resolve/main/model.onnx

# 2. (Optional) Also drop a denoiser model
#    Not required for the default pipeline; reserved for future work.
```

## Why ONNX + DirectML

Using an ONNX vocal-separator on the **same DirectML EP** as Wav2Lip means the
entire pipeline — separator + face detector + Wav2Lip generator — runs on the
AMD GPU with one consistent execution provider and one consistent
`ORT_SEQUENTIAL` session mode. No PyTorch dependency, no CPU fallback, no
device juggling.
