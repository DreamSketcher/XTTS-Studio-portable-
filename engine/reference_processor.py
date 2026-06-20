import os
from pathlib import Path
from pydub import AudioSegment
import shutil
from datetime import datetime


# =========================
# ADAPTIVE SILENCE TRIMMER
# =========================
class AdaptiveSilenceTrimmer:
    def __init__(self):
        self.min_silence_db = -45
        self.hard_limit_ms = 250

    def trim(self, audio: AudioSegment) -> AudioSegment:
        if len(audio) < 300:
            return audio

        noise_floor = audio.dBFS
        silence_thresh = min(self.min_silence_db, noise_floor - 16)

        start_trim = self._find_start(audio, silence_thresh)
        end_trim = self._find_end(audio, silence_thresh)

        start_trim = min(start_trim, self.hard_limit_ms)
        end_trim = min(end_trim, self.hard_limit_ms)

        padding = 40

        start = max(0, start_trim - padding)
        end = len(audio) - max(0, end_trim - padding)

        if end <= start:
            return audio

        return audio[start:end]

    def _find_start(self, audio, silence_thresh):
        step = 10
        for i in range(0, len(audio), step):
            chunk = audio[i:i + step]
            if chunk.dBFS > silence_thresh:
                return i
        return 0

    def _find_end(self, audio, silence_thresh):
        step = 10
        for i in range(len(audio), 0, -step):
            chunk = audio[max(0, i - step):i]
            if chunk.dBFS > silence_thresh:
                return len(audio) - i
        return 0


# =========================
# MAIN PROCESSOR
# =========================
class ReferenceProcessor:
    def __init__(self, backup_dir="library"):
        self.backup_dir = Path(backup_dir).resolve()
        self.backup_dir.mkdir(exist_ok=True)

        # 🔥 adaptive trimmer
        self.trimmer = AdaptiveSilenceTrimmer()

    # =========================
    # VOICE FOLDER
    # =========================
    def get_voice_dir(self, filepath: str) -> Path:
        src = Path(filepath).resolve()

        # если файл уже внутри библиотеки — вернуть его папку
        try:
            src.relative_to(self.backup_dir)
            return src.parent
        except ValueError:
            pass

        voice_dir = self.backup_dir / src.stem
        voice_dir.mkdir(parents=True, exist_ok=True)
        return voice_dir
    # =========================
    # SAVE ORIGINAL
    # =========================
    def save_original_copy(self, filepath: str, voice_dir: Path) -> str:
        src = Path(filepath).resolve()
        if src.suffix.lower() == ".wav":
            return str(src)

        dst = voice_dir / src.name
        if not dst.exists():
            shutil.copy2(src, dst)

        return str(dst)

    # =========================
    # CONVERT TO WAV (FIXED)
    # =========================
    def convert_to_wav(
        self,
        filepath: str,
        voice_dir: Path,
        target_sample_rate=24000,
        mono=True
    ) -> str:

        import gc
        import time
        from pydub import AudioSegment

        audio = AudioSegment.from_file(filepath)

        if mono:
            audio = audio.set_channels(1)

        audio = audio.set_frame_rate(target_sample_rate)

        out_path = voice_dir / "converted.wav"

        # 🔥 Windows-safe delete (with retry)
        if out_path.exists():
            for _ in range(20):
                try:
                    out_path.unlink()
                    break
                except PermissionError:
                    time.sleep(0.05)

        audio.export(out_path, format="wav")

        # 🔥 release ffmpeg handle
        del audio
        gc.collect()

        return str(out_path)    

    # =========================
    # PROCESS AUDIO (CLEAN + NORMALIZE)
    # =========================
    def process_audio(self, filepath: str, voice_dir: Path,
                target_dBFS=-16.0) -> str:

        import gc
        import time
        from pydub import AudioSegment
        from pydub.effects import compress_dynamic_range

        audio = AudioSegment.from_file(filepath)

        audio = self.trimmer.trim(audio)

        duration_sec = len(audio) / 1000

        if duration_sec > 30:
            audio = audio[:30000]

        # компрессия динамического диапазона референса —
        # сглаживает внутренние просадки/всплески громкости,
        # которые модель иначе "копирует" в генерацию
        audio = compress_dynamic_range(
            audio,
            threshold=-24.0,
            ratio=3.0,
            attack=5.0,
            release=50.0
        )

        gain = target_dBFS - audio.dBFS
        audio = audio.apply_gain(gain)

        out_path = voice_dir / "normalized.wav"
        tmp_path = voice_dir / "normalized_tmp.wav"

        audio.export(tmp_path, format="wav")

        # 🔥 CRITICAL FIX: retry delete (Windows lock fix)
        if out_path.exists():
            for _ in range(30):
                try:
                    out_path.unlink()
                    break
                except PermissionError:
                    time.sleep(0.05)

        # 🔥 rename with retry (THIS is where WinError 32 usually happens)
        for _ in range(30):
            try:
                tmp_path.replace(out_path)
                break
            except PermissionError:
                time.sleep(0.05)

        # 🔥 release file handle
        del audio
        gc.collect()

        return str(out_path)

    # =========================
    # PIPELINE
    # =========================
    def process_reference(self, filepath: str, backup=True) -> str:

        filepath = str(Path(filepath).resolve())
        voice_dir = self.get_voice_dir(filepath)

        if backup:
            self.save_original_copy(filepath, voice_dir)

        working = self.convert_to_wav(filepath, voice_dir)
        working = self.process_audio(working, voice_dir)

        return str(Path(working).resolve())