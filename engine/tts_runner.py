import re
import os
import sys
from datetime import datetime
from engine.prosody_layer import create_prosody_layer
from .word_replacer import WordReplacer

# =========================
# SAFE PYTHON ISOLATION
# =========================
os.environ["PYTHONHOME"] = ""
os.environ["PYTHONNOUSERSITE"] = "1"
os.environ["PYTHONEXECUTABLE"] = sys.executable

os.environ["PATH"] = (
    os.path.dirname(sys.executable)
    + os.pathsep
    + os.environ.get("PATH", "")
)

# =========================
# COQUI FIX (CRITICAL)
# =========================
os.environ["COQUI_TOS_AGREED"] = "1"
os.environ["TTS_SKIP_UPDATE"] = "1"

# =========================
# OPTIONAL BACKEND
# =========================
try:
    from pydub import AudioSegment
    PYDUB_OK = True
except ImportError:
    PYDUB_OK = False

# =========================
# LOCAL MODULES
# =========================
from .normalizer import TextNormalizer
from .chunker import TextChunker
from .smart_pauses import SmartPauseEngine
from .reference_processor import ReferenceProcessor

# =========================
# BASE PATH
# =========================
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(__file__))

def path(*args):
    return os.path.join(BASE_DIR, *args)

# =========================
# FFMPEG
# =========================
FFMPEG_DIR = path("ffmpeg", "bin")
os.environ["PATH"] = FFMPEG_DIR + os.pathsep + os.environ.get("PATH", "")

if PYDUB_OK:
    AudioSegment.converter = path("ffmpeg", "bin", "ffmpeg.exe")
    AudioSegment.ffprobe   = path("ffmpeg", "bin", "ffprobe.exe")

# =========================
# COMPONENTS
# =========================
normalizer    = TextNormalizer()
chunker       = TextChunker()
pause_engine  = SmartPauseEngine()
ref_processor = ReferenceProcessor(backup_dir=path("library"))
word_replacer = WordReplacer(rules_path=path("word_rules.json"))

# =========================
# MODEL
# =========================
import threading as _threading

MODEL_DIR = path("models", "xtts_v2")

_tts_instance = None
_tts_lock = _threading.Lock()

def detect_lang_adaptive(text: str) -> str:
    return "ru" if any('\u0400' <= c <= '\u04FF' for c in text) else "en"

def get_tts():
    global _tts_instance

    with _tts_lock:
        if _tts_instance is None:
            print("[XTTS] Loading model...")

            from TTS.api import TTS

            if not os.path.exists(MODEL_DIR):
                raise RuntimeError(f"Model not found: {MODEL_DIR}")

            _tts_instance = TTS(
                model_path=MODEL_DIR,
                config_path=os.path.join(MODEL_DIR, "config.json"),
                gpu=False
            )

    return _tts_instance

# =========================
# CANCELLATION EXCEPTION
# =========================
class _Cancelled(Exception):
    pass

# =========================
# EMBEDDING CACHE
# =========================
def _get_embedding(tts, ref_wav, cache_path):
    if os.path.exists(cache_path):
        try:
            import torch
            data = torch.load(cache_path, map_location="cpu")
            print("[XTTS] Embedding loaded from cache")
            return data["gpt_cond_latent"], data["speaker_embedding"]
        except Exception as e:
            print(f"[XTTS] Cache load failed, recomputing: {e}")

    print("[XTTS] Computing embedding...")
    import torch
    gpt_cond_latent, speaker_embedding = (
        tts.synthesizer.tts_model.get_conditioning_latents(audio_path=ref_wav)
    )
    try:
        torch.save({
            "gpt_cond_latent":   gpt_cond_latent,
            "speaker_embedding": speaker_embedding
        }, cache_path)
        print("[XTTS] Embedding saved to cache")
    except Exception as e:
        print(f"[XTTS] Cache save failed: {e}")

    return gpt_cond_latent, speaker_embedding

# =========================
# QUALITY PRESETS
# =========================

PROSODY_PRESETS = {
    "Высокое качество": dict(mode="balanced",     intensity=0.1),
    "Нарратив":         dict(mode="balanced",     intensity=0.5),
    "Динамика":         dict(mode="balanced",     intensity=1.1),
    "Экспрессия":       dict(mode="studio_ultra", intensity=1.3),
}

# =========================
# ADAPTIVE TRIM
# =========================
def _adaptive_trim(
    seg,
    chunk_text="",
    base_ms=100,
    mode="auto",
    range_ms=30,
    silence_thresh_db=-35.0
):
    if len(seg) < 100:
        return seg

    mode = str(mode or "auto").lower()

    if mode in ("off", "none", "disable", "disabled", "false", "0"):
        return seg

    base_ms = int(base_ms or 0)
    range_ms = int(range_ms or 0)

    if base_ms <= 0:
        return seg

    if mode == "manual":
        if len(seg) > base_ms:
            return seg[:-base_ms].fade_out(min(40, base_ms))
        return seg

    text = chunk_text.strip()

    if text and text[-1] in ".!?":
        keep_silence_ms = 120
    elif text and text[-1] == ",":
        keep_silence_ms = 60
    else:
        keep_silence_ms = 80

    speech_thresh_db = silence_thresh_db
    tail_silence_thresh = silence_thresh_db - 10

    step = 10
    max_trim = base_ms + range_ms

    artifact_end = len(seg)

    # Ищем последнюю речь в хвосте
    for pos in range(len(seg), max(0, len(seg) - 300), -step):
        chunk = seg[max(0, pos - step):pos]
        if chunk.dBFS > speech_thresh_db:
            artifact_end = pos
            break

    artifact_start = artifact_end

    # Ищем тишину перед артефактом/хвостом
    for pos in range(artifact_end, max(0, artifact_end - 500), -step):
        chunk = seg[max(0, pos - step):pos]
        if chunk.dBFS <= tail_silence_thresh:
            artifact_start = pos
            break

    silence_start = artifact_start

    # Ищем последнюю речь перед тишиной
    for pos in range(artifact_start, max(0, artifact_start - 500), -step):
        chunk = seg[max(0, pos - step):pos]
        if chunk.dBFS > speech_thresh_db:
            silence_start = pos
            break

    cut_point = silence_start + keep_silence_ms
    trim_ms = len(seg) - cut_point

    # Важно: не заставляем auto-trim резать минимум всегда.
    # Иначе он может съедать окончания слов, если тишина не найдена.
    if trim_ms <= 0:
        return seg

    trim_ms = min(trim_ms, max_trim)

    if trim_ms > 0 and len(seg) > trim_ms:
        return seg[:-int(trim_ms)].fade_out(min(40, int(trim_ms)))

    return seg

# =========================
# ENGINE
# =========================
def run_tts(
    text,
    ref_path,
    model_key=None,
    status_callback=None,
    is_cancelled=None,
    speed=1.0,
    language="auto",
    quality="Высокое качество",
    quality_params=None
):
    def cancelled() -> bool:
        return callable(is_cancelled) and is_cancelled()

    def send(stage, progress=None, text_msg=None, final=None):
        if status_callback:
            status_callback({
                "stage":    stage,
                "progress": progress,
                "text":     text_msg,
                "final":    final,
            })

    def cleanup(files: list):
        for f in files:
            try:
                os.remove(f)
            except Exception:
                pass
            

    import time
    gen_start = time.time()

    try:
        tts = get_tts()

        # =========================
        # REFERENCE (0–10%)
        # =========================
        if cancelled(): raise _Cancelled()
        send("reference", 0, "Обработка reference...")
        ref_wav = ref_processor.process_reference(ref_path)
        send("reference", 10)

        # =========================
        # NORMALIZE (10–20%)
        # =========================
        if cancelled(): raise _Cancelled()
        send("normalize", 10, "Нормализация текста...")
        text = word_replacer.apply(text)
        text = normalizer.normalize(text)
        send("normalize", 20)

        # =========================
        # CHUNKING (20–30%)
        # =========================
        if cancelled(): raise _Cancelled()
        send("chunking", 20, "Разбиение текста...")

        chunks_before_prosody = chunker.chunk_text(text)

        map_text = re.sub(r"[ \t]+", " ", text)
        chunk_map = []
        search_from = 0
        for c in chunks_before_prosody:
            key = c.strip()[:20]
            pos = map_text.find(key, search_from)
            if pos != -1:
                chunk_map.append((pos, pos + len(c.strip())))
                search_from = pos + 1
            else:
                last = chunk_map[-1][1] if chunk_map else 0
                chunk_map.append((last, last))

        lang_detected = detect_lang_adaptive(text)
        prosody_preset = PROSODY_PRESETS.get(
            quality,
            PROSODY_PRESETS["Высокое качество"]
        )
        prosody_intensity = quality_params.get("prosody_intensity", prosody_preset["intensity"]) if quality_params else prosody_preset["intensity"]
        prosody_engine = create_prosody_layer(
            mode=prosody_preset["mode"],
            intensity=prosody_intensity,
            breath_length="medium"
        )
        chunks = [prosody_engine.process(c, lang=lang_detected) for c in chunks_before_prosody]

        send("chunking", 30)

        output_dir = path("outputs")
        os.makedirs(output_dir, exist_ok=True)

        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        final_path = os.path.join(output_dir, f"output_{ts}.wav")

        total = max(len(chunks), 1)
        chunk_items = []

        # =========================
        # GENERATION (30–90%)
        # =========================
        send("generate", 30, "Генерация аудио...")

        cache_path = os.path.splitext(ref_wav)[0] + "_embedding.pth"
        gpt_cond_latent, speaker_embedding = _get_embedding(tts, ref_wav, cache_path)

        for i, chunk in enumerate(chunks):

            if cancelled():
                cleanup([item["path"] for item in chunk_items])
                raise _Cancelled()

            if len(chunk.strip()) < 5:
                continue

            start, end = chunk_map[i] if i < len(chunk_map) else (0, 0)

            if status_callback:
                status_callback({
                    "stage": "chunk",
                    "chunk_index": i,
                    "chunk_start": start,
                    "chunk_end": end,
                })

            chunk_path = os.path.join(output_dir, f"_chunk_{i}.wav")
            lang = detect_lang_adaptive(chunk) if language == "auto" else language

            print(f"[Chunk {i+1}/{total}] {chunk}")

            try:
                preset = dict(quality_params or {})

                speed_value = preset.pop("speed", speed)

                trim_ms = int(preset.pop("trim_ms", 80) or 0)
                trim_mode = str(preset.pop("trim_mode", "auto") or "auto").lower()

                # их нельзя передавать в XTTS inference.
                preset.pop("prosody_intensity", None)
                preset.pop("trim_range_ms", None)
                preset.pop("silence_thresh_db", None)

                out = tts.synthesizer.tts_model.inference(
                    text=chunk,
                    language=lang,
                    gpt_cond_latent=gpt_cond_latent,
                    speaker_embedding=speaker_embedding,
                    speed=speed_value,
                    **preset
                )

                import soundfile as sf

                wav = out["wav"]

                # Не режем здесь, если доступен pydub.
                # Adaptive trim будет выполнен позже при merge.
                if not PYDUB_OK:
                    if trim_mode not in ("off", "none", "disable", "disabled", "false", "0"):
                        trim_samples = int(24000 * trim_ms / 1000)
                        if trim_samples > 0 and len(wav) > trim_samples:
                            wav = wav[:-trim_samples]

                sf.write(chunk_path, wav, 24000)

                chunk_items.append({
                    "path": chunk_path,
                    "source_text": chunks_before_prosody[i] if i < len(chunks_before_prosody) else chunk,
                    "processed_text": chunks[i] if i < len(chunks) else chunk,
                })

            except Exception as e:
                print(f"[Chunk {i} error]: {e}")

            progress = 30 + int((i + 1) / total * 60)
            send("generate", progress)

            if not chunk_items:
                raise RuntimeError("No chunks were generated")

        # =========================
        # MERGE (90–100%)
        # =========================
        if cancelled():
            cleanup([item["path"] for item in chunk_items])
            raise _Cancelled()

        send("merge", 90, "Сборка аудио...")

        if PYDUB_OK and chunk_items:
            combined = AudioSegment.empty()

            valid_segments = []
            valid_chunks = []

            trim_ms = int(quality_params.get("trim_ms", 80)) if quality_params else 80
            trim_mode = quality_params.get("trim_mode", "auto") if quality_params else "auto"
            trim_range_ms = int(quality_params.get("trim_range_ms", 15)) if quality_params else 15
            silence_thresh_db = float(quality_params.get("silence_thresh_db", -35.0)) if quality_params else -35.0

            for i, item in enumerate(chunk_items):
                try:
                    seg = AudioSegment.from_wav(item["path"])

                    if len(seg) < 50:
                        continue

                    seg = _adaptive_trim(
                        seg,
                        chunk_text=item["source_text"],
                        base_ms=trim_ms,
                        mode=trim_mode,
                        range_ms=trim_range_ms,
                        silence_thresh_db=silence_thresh_db
                    )

                    # Защита от полностью тихого сегмента
                    if seg.dBFS != float("-inf"):
                        seg = seg.apply_gain(-18.0 - seg.dBFS)

                    valid_segments.append(seg)
                    valid_chunks.append(item["processed_text"])

                except Exception as e:
                    print(f"[Merge chunk load error {i}]: {e}")

            for i, seg in enumerate(valid_segments):
                combined += seg

                if i != len(valid_segments) - 1:
                    pause_ms = pause_engine.get_pause_ms(valid_chunks[i])
                    combined += AudioSegment.silent(pause_ms)

            combined += AudioSegment.silent(200)
            combined = combined.fade_out(80)

            if combined.dBFS != float("-inf"):
                combined = combined.apply_gain(-18.0 - combined.dBFS)

            combined.export(final_path, format="wav")

            cleanup([item["path"] for item in chunk_items])

        else:
            if not chunk_items:
                raise RuntimeError("No audio chunks generated")

            try:
                import soundfile as sf
                import numpy as np

                audio_parts = []
                sample_rate = None

                for i, item in enumerate(chunk_items):
                    data, sr = sf.read(item["path"], dtype="float32")

                    if sample_rate is None:
                        sample_rate = sr
                    elif sr != sample_rate:
                        raise RuntimeError(f"Sample rate mismatch: {sr} != {sample_rate}")

                    audio_parts.append(data)

                    if i != len(chunk_items) - 1:
                        pause_ms = pause_engine.get_pause_ms(item["processed_text"])
                        silence_samples = int(sample_rate * pause_ms / 1000)

                        if data.ndim == 1:
                            silence = np.zeros((silence_samples,), dtype="float32")
                        else:
                            silence = np.zeros((silence_samples, data.shape[1]), dtype="float32")

                        audio_parts.append(silence)

                combined = np.concatenate(audio_parts, axis=0)
                sf.write(final_path, combined, sample_rate)

                cleanup([item["path"] for item in chunk_items])

            except Exception as e:
                cleanup([item["path"] for item in chunk_items])
                raise RuntimeError(f"Fallback merge failed: {e}") from e

        send("generate", 100)

        # статистика
        gen_elapsed = int(time.time() - gen_start)
        voice_name = os.path.basename(os.path.dirname(ref_wav))
        if voice_name.replace("-", "").replace("_", "").isdigit() or "output_" in voice_name:
            voice_name = os.path.splitext(os.path.basename(ref_path))[0]

        if status_callback:
            status_callback({
                "stage":    "stats",
                "progress": 100,
                "time_sec": gen_elapsed,
                "chunks": len(chunk_items),
                "speed":    speed,
                "voice":    voice_name,
                "quality":  quality,
                "text_len": len(text),
            })

        return final_path

    except _Cancelled:
        return None

    except Exception as e:
        raise RuntimeError(f"XTTS ENGINE ERROR: {str(e)}") from e