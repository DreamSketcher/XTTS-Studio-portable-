from pydub import AudioSegment

class AudioStitcher:
    def stitch_chunks(self, chunk_files, fade_ms=50, pause_ms=100, out_file="output.wav"):
        combined = AudioSegment.empty()
        for cf in chunk_files:
            seg = AudioSegment.from_wav(cf)
            seg = seg.fade_in(fade_ms).fade_out(fade_ms)
            combined += seg + AudioSegment.silent(duration=pause_ms)
        combined.export(out_file, format="wav")
