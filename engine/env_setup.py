"""
engine/env_setup.py — анализ окружения и (пере)установка зависимостей
для локальных LLM (llama-cpp-python), с учётом набора инструкций CPU.

Без tkinter — чистая логика, чтобы её можно было гонять и из консоли/тестов.
Импорт llama_cpp проверяется в ОТДЕЛЬНОМ процессе (subprocess), а не в текущем —
если сборка несовместима с CPU (illegal instruction), крашится только проверочный
процесс, а не всё приложение.
"""

import os
import sys
import subprocess
import shutil

from engine.paths import BASE_DIR

SITE_PACKAGES = os.path.join(BASE_DIR, "python", "xtts_env", "Lib", "site-packages")
PYTHON_EXE = sys.executable  # тот же интерпретатор, что запустил приложение (python\runtime\python.exe)


def _ensure_cpuinfo() -> bool:
    """py-cpuinfo — чистый python-пакет, компиляция не нужна, ставится за секунды."""
    sys.path.insert(0, SITE_PACKAGES)
    try:
        import cpuinfo  # noqa: F401
        return True
    except ImportError:
        try:
            subprocess.run(
                [PYTHON_EXE, "-m", "pip", "install", "py-cpuinfo",
                 "--no-cache-dir", "--target", SITE_PACKAGES],
                check=True, capture_output=True, timeout=60, text=True,
            )
            return True
        except Exception:
            return False


def detect_cpu() -> dict:
    """
    {"name": str, "avx": bool, "avx2": bool, "fma": bool, "f16c": bool, "flags": set}
    Если флаги определить не удалось — считаем их отсутствующими (безопасный минимум,
    сборка получится медленнее, но не упадёт).
    """
    result = {"name": "не определено", "flags": set(),
              "avx": False, "avx2": False, "fma": False, "f16c": False}

    if _ensure_cpuinfo():
        try:
            import cpuinfo
            info = cpuinfo.get_cpu_info()
            result["name"] = info.get("brand_raw", "не определено")
            flags = set(info.get("flags", []))
            result["flags"] = flags
            result["avx"] = "avx" in flags
            result["avx2"] = "avx2" in flags
            result["fma"] = "fma" in flags or "fma3" in flags
            result["f16c"] = "f16c" in flags
        except Exception:
            pass

    return result


def llama_cpp_status() -> dict:
    """Проверка импорта в ОТДЕЛЬНОМ процессе — изолирует возможный hard crash."""
    probe = (
        "import sys; sys.path.insert(0, r'%s'); "
        "import llama_cpp; print(llama_cpp.__file__)" % SITE_PACKAGES
    )
    try:
        proc = subprocess.run(
            [PYTHON_EXE, "-c", probe],
            capture_output=True, text=True, timeout=15,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return {"installed": True, "path": proc.stdout.strip(), "error": None}
        err = (proc.stderr or "").strip()
        if proc.returncode < 0:
            err = f"процесс завершён аварийно (код {proc.returncode}) — {err}"
        return {"installed": False, "path": None, "error": err or f"exit code {proc.returncode}"}
    except subprocess.TimeoutExpired:
        return {"installed": False, "path": None, "error": "проверка не уложилась в таймаут"}
    except Exception as e:
        return {"installed": False, "path": None, "error": str(e)}


def build_cmake_args(cpu: dict) -> str:
    flags = []
    if not cpu.get("avx2"): flags.append("-DGGML_AVX2=OFF")
    if not cpu.get("fma"): flags.append("-DGGML_FMA=OFF")
    if not cpu.get("f16c"): flags.append("-DGGML_F16C=OFF")
    if not cpu.get("avx"): flags.append("-DGGML_AVX=OFF")
    return " ".join(flags)


def _clean_previous_install():
    """Сносит остатки предыдущей установки — иначе pip --target молча не перезаписывает файлы."""
    if not os.path.isdir(SITE_PACKAGES):
        return
    for name in os.listdir(SITE_PACKAGES):
        if name.startswith("llama_cpp"):
            full = os.path.join(SITE_PACKAGES, name)
            shutil.rmtree(full, ignore_errors=True) if os.path.isdir(full) else \
                (os.remove(full) if os.path.isfile(full) else None)
    # bin/include/lib — общие подпапки llama-cpp-python; трогаем, только если там его DLL
    for name in ("bin", "include", "lib"):
        full = os.path.join(SITE_PACKAGES, name)
        if os.path.isdir(full):
            try:
                if any(f.lower().startswith(("ggml", "llama")) for f in os.listdir(full)):
                    shutil.rmtree(full, ignore_errors=True)
            except Exception:
                pass


def install_llama_cpp(progress_cb=None) -> dict:
    """
    Пересобирает llama-cpp-python под инструкции текущего CPU.
    progress_cb(line: str) — вызывается на каждую строку вывода (для лога в UI).
    Бросает RuntimeError при неуспехе. Возвращает llama_cpp_status() при успехе.
    """
    def emit(line):
        if progress_cb:
            progress_cb(line)

    cpu = detect_cpu()
    cmake_args = build_cmake_args(cpu)

    emit(f"CPU: {cpu['name']}")
    emit(f"Отключаемые наборы инструкций: {cmake_args or '(нет — CPU поддерживает всё нужное)'}")
    emit("Удаляю предыдущую установку (если была)...")
    _clean_previous_install()

    env = os.environ.copy()
    if cmake_args:
        env["CMAKE_ARGS"] = cmake_args

    cmd = [
        PYTHON_EXE, "-m", "pip", "install", "llama-cpp-python",
        "--no-deps", "--no-cache-dir", "--target", SITE_PACKAGES,
    ]
    emit("Устанавливаю (компиляция может занять несколько минут)...")

    proc = subprocess.Popen(
        cmd, cwd=BASE_DIR, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )
    for line in proc.stdout:
        emit(line.rstrip())
    proc.wait()

    if proc.returncode != 0:
        raise RuntimeError(f"pip завершился с кодом {proc.returncode}")

    emit("Проверяю импорт (в отдельном процессе)...")
    status = llama_cpp_status()
    if not status["installed"]:
        raise RuntimeError(f"Установка прошла, но импорт не удался: {status['error']}")

    emit("✅ Готово — llama-cpp-python собран и работает на этом CPU.")
    return status

def detect_gpu() -> dict:
    """
    {"vendor": "nvidia" | "amd" | "intel" | "unknown",
     "name": str,
     "cuda_version": str | None}   # только для vendor == "nvidia"

    Порядок проверки: сначала nvidia-smi (ставится вместе с драйвером NVIDIA,
    отдельно ничего просить не надо). Если его нет — смотрим на любой
    видеоадаптер через WMI (PowerShell CIM), там же выцепляем AMD/Intel.
    Если ничего не нашли — считаем "unknown", это ведёт к CPU-варианту.
    """
    result = {"vendor": "unknown", "name": "не определено", "cuda_version": None}

    # ── NVIDIA ──────────────────────────────────────────────────────────────
    try:
        proc = subprocess.run(
            ["nvidia-smi"],
            capture_output=True, text=True, timeout=10,
        )
        if proc.returncode == 0 and proc.stdout:
            out = proc.stdout
            result["vendor"] = "nvidia"

            # Имя карты: строка вида "| N%   xx°C  ...  NVIDIA GeForce RTX 3060 ..."
            for line in out.splitlines():
                if "NVIDIA" in line and ("GeForce" in line or "RTX" in line or "GTX" in line or "Quadro" in line or "Tesla" in line):
                    parts = [p.strip() for p in line.split("|") if p.strip()]
                    if len(parts) >= 2:
                        result["name"] = parts[1].split("  ")[0].strip()
                    break

            # Версия CUDA: строка вида "CUDA Version: 12.4"
            for line in out.splitlines():
                if "CUDA Version" in line:
                    try:
                        result["cuda_version"] = line.split("CUDA Version:")[1].strip().split()[0].rstrip("|").strip()
                    except Exception:
                        pass
                    break

            return result
    except FileNotFoundError:
        pass  # nvidia-smi отсутствует — не NVIDIA-система (или драйвер не установлен)
    except Exception:
        pass

    # ── AMD / Intel через WMI ────────────────────────────────────────────────
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"],
            capture_output=True, text=True, timeout=15,
        )
        if proc.returncode == 0 and proc.stdout:
            names = [n.strip() for n in proc.stdout.splitlines() if n.strip()]
            for name in names:
                low = name.lower()
                if "amd" in low or "radeon" in low:
                    result["vendor"] = "amd"
                    result["name"] = name
                    return result
                if "intel" in low:
                    result["vendor"] = "intel"
                    result["name"] = name
                    return result
            if names:
                result["name"] = names[0]
    except Exception:
        pass

    return result