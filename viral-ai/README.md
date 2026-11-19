# Mano Clip Tool — Free Local Viral AI

This optional local service adds genuine speech transcription and AI moment selection. It does not require a paid API or subscription.

## One-time setup (Windows)

1. Install Python 3.10–3.12 and enable **Add Python to PATH**.
2. Install Ollama from https://ollama.com/download.
3. Open Command Prompt and run:
   `ollama pull qwen2.5:3b`
4. Double-click `start-mano-ai.bat` in this folder. The first run installs Python packages and downloads the Whisper `small` model; this can take time and several GB of disk space.
5. Keep the black terminal window open while using Mano Clip Tool.

The local service runs at `http://127.0.0.1:8765`. Check setup at `http://127.0.0.1:8765/health`.

## Models and performance

- Whisper `small` transcribes speech locally, including timestamped segments. Set `MANO_WHISPER_MODEL=base` for a smaller/faster but less accurate model, or `medium` for better accuracy on a capable PC.
- Ollama `qwen2.5:3b` ranks timestamped transcript moments locally. You can change `MANO_OLLAMA_MODEL` before starting the server.
- No video is sent to a cloud API. Processing speed depends on your CPU, RAM, and GPU. Long videos can take considerable time.
- AI scores are editorial estimates, not a promise that a clip will go viral.

## Troubleshooting

- If Ollama is not running, open the Ollama app and run `ollama pull qwen2.5:3b`.
- If Whisper installation fails, install the Microsoft Visual C++ Redistributable and retry.
- If your computer has limited RAM, use Whisper `base` and Ollama `qwen2.5:1.5b`.
- The browser page and local AI service must run on the same Windows computer.

This service is separate from the existing video/audio playback and clip export code.
