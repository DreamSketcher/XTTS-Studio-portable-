def __init__(self, backup_dir="library"):
    # =========================
    # BASE PATH
    # =========================
    self.backup_dir = Path(backup_dir).resolve()
    self.backup_dir.mkdir(exist_ok=True)

    # =========================
    # AUDIO TOOLS (PIPELINE COMPONENTS)
    # =========================

    # адаптивный триммер тишины (убирает хвосты XTTS и шум)
    self.trimmer = AdaptiveSilenceTrimmer()

    # (опционально задел на будущее)
    # сюда потом можно добавить:
    # self.eq = AudioEqualizer()
    # self.noise_reducer = NoiseReducer()
    # self.limiter = AudioLimiter()