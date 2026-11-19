from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

import requests
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from faster_whisper import WhisperModel

APP_DIR = Path(__file__).resolve().parent
WHISPER_MODEL = os.getenv("MANO_WHISPER_MODEL", "small")
OLLAMA_MODEL = os.getenv("MANO_OLLAMA_MODEL", "qwen2.5:3b")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
DEVICE = os.getenv("MANO_WHISPER_DEVICE", "auto")
COMPUTE_TYPE = os.getenv("MANO_WHISPER_COMPUTE", "int8")

app = FastAPI(title="Mano Clip Tool - Free Viral AI", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_whisper: WhisperModel | None = None


def get_whisper() -> WhisperModel:
    global _whisper
    if _whisper is None:
        _whisper = WhisperModel(
            WHISPER_MODEL, device=DEVICE, compute_type=COMPUTE_TYPE,
            download_root=str(APP_DIR / "models")
        )
    return _whisper


def transcribe_full_video(path: str) -> list[dict[str, Any]]:
    model = get_whisper()
    segments, _info = model.transcribe(
        path, beam_size=5, word_timestamps=True, vad_filter=True,
        condition_on_previous_text=True
    )
    rows: list[dict[str, Any]] = []
    for seg in segments:
        text = (seg.text or "").strip()
        if not text:
            continue
        rows.append({
            "start": round(float(seg.start), 2),
            "end": round(float(seg.end), 2),
            "text": text
        })
    return rows


def ask_local_ai(transcript: list[dict[str, Any]], count: int, duration: int) -> list[dict[str, Any]]:
    # Send timestamped transcript in manageable chunks so long podcasts are covered.
    chunks: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    chunk_start = 0.0
    for item in transcript:
        if current and item["end"] - chunk_start > 420:
            chunks.append(current)
            current = []
            chunk_start = item["start"]
        if not current:
            chunk_start = item["start"]
        current.append(item)
    if current:
        chunks.append(current)

    candidates: list[dict[str, Any]] = []
    for chunk_no, chunk in enumerate(chunks, start=1):
        transcript_text = "\n".join(
            f'[{x["start"]:.2f}-{x["end"]:.2f}] {x["text"]}' for x in chunk
        )
        prompt = f"""
You are a highly selective short-form video editor. Analyze this timestamped spoken transcript chunk ({chunk_no}/{len(chunks)}).
Find up to {max(count * 2, 6)} genuinely compelling, self-contained moments that could hold attention in a TikTok/YouTube Short.
Prioritize: surprising revelations, strong opinions, emotional honesty, funny exchanges, conflict/tension, useful concrete advice, unexpected turns, vivid stories, bold claims, and curiosity-provoking complete statements.
Reject greetings, introductions, filler, contextless fragments, repeated points, ads, and ordinary small talk.
A moment must make sense without relying on missing audio. Keep exact source timestamps. Return JSON only:
{{"moments":[{{"start":12.3,"end":39.8,"hook":"short accurate title","reason":"why this moment is compelling","category":"story|surprise|opinion|emotion|humor|advice|conflict","score":0}}]}}
Scores are editorial estimates from 0 to 100, not guarantees of virality. Do not invent quotes or timestamps.
Transcript:
{transcript_text}
"""
        try:
            response = requests.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.15, "num_ctx": 12000}
                },
                timeout=900
            )
            response.raise_for_status()
            content = response.json()["message"]["content"]
            parsed = json.loads(content)
            for m in parsed.get("moments", []):
                try:
                    start = float(m["start"])
                    end = float(m["end"])
                    score = int(max(0, min(100, float(m.get("score", 50)))))
                    if end > start and any(x["start"] <= start <= x["end"] for x in chunk):
                        candidates.append({
                            "start": start, "end": end,
                            "hook": str(m.get("hook", "Interesting moment"))[:120],
                            "reason": str(m.get("reason", ""))[:300],
                            "category": str(m.get("category", "story"))[:30],
                            "score": score
                        })
                except (TypeError, ValueError, KeyError):
                    continue
        except requests.RequestException as exc:
            raise RuntimeError(
                "Ollama is not running. Open Ollama and make sure model "
                f"{OLLAMA_MODEL} is installed. Details: {exc}"
            ) from exc
        except (ValueError, KeyError, json.JSONDecodeError):
            continue

    # Remove duplicates and overlapping moments; favor strong, distinct topics.
    candidates.sort(key=lambda x: x["score"], reverse=True)
    chosen: list[dict[str, Any]] = []
    for item in candidates:
        midpoint = (item["start"] + item["end"]) / 2
        if all(
            abs(midpoint - (x["start"] + x["end"]) / 2) >= max(18, duration * 0.8)
            and not (item["start"] < x["end"] and item["end"] > x["start"])
            for x in chosen
        ):
            chosen.append(item)
        if len(chosen) >= count:
            break
    chosen.sort(key=lambda x: x["start"])
    return chosen


@app.get("/health")
def health() -> dict[str, Any]:
    ollama_ok = False
    installed_models: list[str] = []
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        r.raise_for_status()
        installed_models = [m.get("name", "") for m in r.json().get("models", [])]
        ollama_ok = True
    except requests.RequestException:
        pass
    return {
        "ok": True, "ollama": ollama_ok, "ollama_model": OLLAMA_MODEL,
        "model_installed": any(x == OLLAMA_MODEL or x.startswith(OLLAMA_MODEL + ":") for x in installed_models),
        "whisper_model": WHISPER_MODEL
    }


@app.post("/analyze")
async def analyze(
    video: UploadFile = File(...),
    count: int = Form(3),
    duration: int = Form(30)
) -> dict[str, Any]:
    if count not in (3, 5):
        raise HTTPException(400, "Clip count must be 3 or 5.")
    duration = max(15, min(90, duration))
    suffix = Path(video.filename or "upload.mp4").suffix or ".mp4"
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            temp_path = tmp.name
            while True:
                block = await video.read(1024 * 1024)
                if not block:
                    break
                tmp.write(block)
        transcript = transcribe_full_video(temp_path)
        if not transcript:
            raise HTTPException(422, "No clear speech was detected in this video.")
        moments = ask_local_ai(transcript, count, duration)
        if not moments:
            raise HTTPException(
                422,
                "AI could not find enough distinct strong moments. Try a clearer video or check the local AI model."
            )
        results = []
        for i, moment in enumerate(moments):
            # Start at the AI-selected spoken moment. Existing renderer keeps its own duration.
            results.append({
                "id": f"viral-ai-{i+1}",
                "startSec": max(0, moment["start"]),
                "score": moment["score"],
                "hook": moment["hook"],
                "reason": moment["reason"],
                "category": moment["category"],
                "duration": f"0:{duration:02d}",
                "lines": []
            })
        return {
            "success": True, "transcriptSegments": len(transcript),
            "videoDuration": transcript[-1]["end"], "clips": results
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
