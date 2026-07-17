import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from engine.rvc_pipeline import (
    RVCPostProcessor,
    RVCPipelineError,
    XTTSWithRVCPipeline,
    is_rvc_checkpoint_trusted,
    mark_rvc_checkpoint_trusted,
)


def _write_trusted(path: Path, content: str = "fake"):
    path.write_text(content)
    mark_rvc_checkpoint_trusted(str(path), source="unit-test")


class TestRVCCheckpointTrust:
    def test_unsigned_checkpoint_is_rejected(self, tmp_path):
        model = tmp_path / "unsigned.pth"
        model.write_bytes(b"checkpoint")
        proc = RVCPostProcessor(models_dir=str(tmp_path), device="cpu:0")
        with pytest.raises(RVCPipelineError, match="не подтверждён"):
            proc.run_inference_via_lib("in.wav", "out.wav", "unsigned")

    def test_trust_is_bound_to_exact_sha256(self, tmp_path):
        model = tmp_path / "model.pth"
        model.write_bytes(b"original")
        mark_rvc_checkpoint_trusted(str(model), source="explicit-test")
        assert is_rvc_checkpoint_trusted(str(model)) is True
        model.write_bytes(b"replaced")
        assert is_rvc_checkpoint_trusted(str(model)) is False


class TestRVCPostProcessorDevice:
    def test_normalize_cpu(self):
        assert RVCPostProcessor._normalize_device("cpu") == "cpu:0"
        assert RVCPostProcessor._normalize_device("cpu:0") == "cpu:0"
        assert RVCPostProcessor._normalize_device("CPU") == "cpu:0"
        assert RVCPostProcessor._normalize_device("") == "cpu:0"

    def test_normalize_cuda(self):
        assert RVCPostProcessor._normalize_device("cuda") == "cuda:0"
        assert RVCPostProcessor._normalize_device("gpu") == "cuda:0"
        assert RVCPostProcessor._normalize_device("cuda0") == "cuda:0"
        assert RVCPostProcessor._normalize_device("cuda:1") == "cuda:1"

    def test_normalize_other(self):
        assert RVCPostProcessor._normalize_device("cuda:0") == "cuda:0"
        assert RVCPostProcessor._normalize_device("custom:1") == "custom:1"


class TestRVCPostProcessorPaths:
    def test_init_creates_dir(self, tmp_path):
        models_dir = tmp_path / "rvc_models"
        proc = RVCPostProcessor(models_dir=str(models_dir), device="cpu:0")
        assert models_dir.exists()
        assert proc.device == "cpu:0"

    @pytest.mark.parametrize(
        "name",
        ["../outside", r"..\outside", "/absolute", r"C:\temp\model", "model.pth", "a:b", ""],
    )
    def test_rejects_unsafe_model_names(self, tmp_path, name):
        proc = RVCPostProcessor(models_dir=str(tmp_path), device="cpu:0")
        with pytest.raises(RVCPipelineError, match="имя|путь"):
            proc.run_inference_via_lib("in.wav", "out.wav", name)

    def test_model_not_found(self, tmp_path, monkeypatch):
        proc = RVCPostProcessor(models_dir=str(tmp_path), device="cpu:0")
        # мок rvc_python чтобы импорт прошёл, и тогда проверка файла сработает
        import sys, types

        fake_mod = types.ModuleType("rvc_python.infer")
        fake_mod.RVCInference = MagicMock()
        monkeypatch.setitem(sys.modules, "rvc_python.infer", fake_mod)
        monkeypatch.setitem(sys.modules, "rvc_python", types.ModuleType("rvc_python"))

        with pytest.raises(RVCPipelineError, match="не найдена"):
            proc.run_inference_via_lib(
                input_path="/tmp/in.wav",
                output_path="/tmp/out.wav",
                model_name="nonexistent",
            )


class TestRunInferenceViaLib:
    def test_import_error(self, tmp_path, monkeypatch):
        proc = RVCPostProcessor(models_dir=str(tmp_path), device="cpu:0")
        # создаём модель файл чтобы пройти первую проверку
        _write_trusted(tmp_path / "test.pth")

        # мокаем отсутствие rvc_python
        import sys

        # удаляем если есть
        monkeypatch.delitem(sys.modules, "rvc_python.infer", raising=False)
        monkeypatch.delitem(sys.modules, "rvc_python", raising=False)

        # патчим __import__ чтобы кидал ImportError для rvc_python
        original_import = __import__

        def fake_import(name, *args, **kwargs):
            if "rvc_python" in name:
                raise ImportError("no rvc_python")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", fake_import)

        with pytest.raises(RVCPipelineError, match="не установлена"):
            proc.run_inference_via_lib("/tmp/in.wav", "/tmp/out.wav", "test")

    def test_success_mocked(self, tmp_path, monkeypatch):
        proc = RVCPostProcessor(models_dir=str(tmp_path), device="cpu:0")
        model_path = tmp_path / "mymodel.pth"
        _write_trusted(model_path, "fake model")
        index_path = tmp_path / "mymodel.index"
        index_path.write_text("fake index")

        input_wav = tmp_path / "in.wav"
        input_wav.write_text("input")
        output_wav = tmp_path / "out.wav"

        # мок RVCInference
        mock_infer = MagicMock()
        mock_infer_instance = MagicMock()
        mock_infer.return_value = mock_infer_instance

        # мок модуля rvc_python.infer
        import sys, types

        fake_module = types.ModuleType("rvc_python.infer")
        fake_module.RVCInference = mock_infer
        monkeypatch.setitem(sys.modules, "rvc_python.infer", fake_module)
        fake_pkg = types.ModuleType("rvc_python")
        fake_pkg.infer = fake_module
        monkeypatch.setitem(sys.modules, "rvc_python", fake_pkg)

        # чтобы проверить что output создаётся, сделаем side effect создания файла
        def fake_infer_file(inp, out):
            Path(out).write_text("output data")

        mock_infer_instance.infer_file.side_effect = fake_infer_file

        result = proc.run_inference_via_lib(
            input_path=str(input_wav),
            output_path=str(output_wav),
            model_name="mymodel",
            index_rate=0.75,
            pitch_shift=0,
            f0_method="rmvpe",
        )

        assert result == str(output_wav)
        assert output_wav.exists()
        mock_infer_instance.load_model.assert_called_once()
        mock_infer_instance.set_params.assert_called_once()

    def test_no_output_file_raises(self, tmp_path, monkeypatch):
        proc = RVCPostProcessor(models_dir=str(tmp_path), device="cpu:0")
        _write_trusted(tmp_path / "model.pth")

        import sys, types

        mock_infer = MagicMock()
        mock_instance = MagicMock()
        mock_infer.return_value = mock_instance
        mock_instance.infer_file.return_value = None  # не создаёт файл

        fake_mod = types.ModuleType("rvc_python.infer")
        fake_mod.RVCInference = mock_infer
        monkeypatch.setitem(sys.modules, "rvc_python.infer", fake_mod)
        monkeypatch.setitem(sys.modules, "rvc_python", types.ModuleType("rvc_python"))

        input_wav = tmp_path / "in.wav"
        input_wav.write_text("in")
        output_wav = tmp_path / "out.wav"

        with pytest.raises(RVCPipelineError, match="без выходного WAV-файла"):
            proc.run_inference_via_lib(str(input_wav), str(output_wav), "model")


class TestRunInferenceViaCli:
    def test_cli_model_not_found(self, tmp_path):
        proc = RVCPostProcessor(models_dir=str(tmp_path))
        with pytest.raises(RVCPipelineError, match="не найдена"):
            proc.run_inference_via_cli("/tmp/in.wav", "/tmp/out.wav", "nonexistent")

    def test_cli_missing_script_raises_not_available(self, tmp_path, monkeypatch):
        """TASK-006: отсутствие tools/RVC_CLI/rvc.py → RVCNotAvailableError
        (а не попытка system python / fallback на «rvc»)."""
        from engine.rvc_pipeline import RVCNotAvailableError

        proc = RVCPostProcessor(models_dir=str(tmp_path))
        _write_trusted(tmp_path / "model.pth")
        # rvc_cli_dir по умолчанию tools/RVC_CLI — относительно cwd теста его нет
        with pytest.raises(RVCNotAvailableError, match="rvc.py"):
            proc.run_inference_via_cli("/tmp/in.wav", "/tmp/out.wav", "model")

    def test_cli_uses_absolute_python_path(self, tmp_path, monkeypatch):
        """TASK-006: cmd[0] — абсолютный PYTHON_EXE, cmd[1] — абсолютный rvc.py."""
        proc = RVCPostProcessor(models_dir=str(tmp_path))
        _write_trusted(tmp_path / "model.pth")

        # создаём фейковый rvc.py, чтобы пройти проверку существования скрипта
        rvc_dir = tmp_path / "tools" / "RVC_CLI"
        rvc_dir.mkdir(parents=True)
        (rvc_dir / "rvc.py").write_text("# stub")

        captured = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            (Path(kwargs.get("capture_output") and "n/a" or "")).exists() if False else None
            return MagicMock(returncode=0, stdout="", stderr="")

        # создаём выходной файл, чтобы CLI «успешно завершился»
        out = tmp_path / "out.wav"

        def fake_run_creates(cmd, **kwargs):
            captured["cmd"] = cmd
            out.write_text("output data")
            return MagicMock(returncode=0, stdout="", stderr="")

        monkeypatch.setattr("subprocess.run", fake_run_creates)

        result = proc.run_inference_via_cli(
            "/tmp/in.wav", str(out), "model", rvc_cli_dir=str(rvc_dir)
        )
        assert result == str(out)
        # оба ключевых пути — абсолютные
        assert os.path.isabs(captured["cmd"][0])
        assert os.path.isabs(captured["cmd"][1])
        assert captured["cmd"][1].endswith("rvc.py")

    def test_cli_success_mocked(self, tmp_path, monkeypatch):
        proc = RVCPostProcessor(models_dir=str(tmp_path))
        _write_trusted(tmp_path / "model.pth")

        rvc_dir = tmp_path / "tools" / "RVC_CLI"
        rvc_dir.mkdir(parents=True)
        (rvc_dir / "rvc.py").write_text("# stub")

        output_wav = tmp_path / "out.wav"

        # subprocess.run в реальности запускает CLI, который и создаёт WAV;
        # мок должен повторить этот побочный эффект, иначе код закономерно
        # решит, что конвертация не удалась (файла нет).
        def fake_run(*a, **kw):
            output_wav.write_text("output data")
            return MagicMock(returncode=0, stdout="", stderr="")

        monkeypatch.setattr("subprocess.run", fake_run)

        result = proc.run_inference_via_cli(
            "/tmp/in.wav", str(output_wav), "model", rvc_cli_dir=str(rvc_dir)
        )
        assert result == str(output_wav)

    def test_cli_failure(self, tmp_path, monkeypatch):
        proc = RVCPostProcessor(models_dir=str(tmp_path))
        _write_trusted(tmp_path / "model.pth")

        rvc_dir = tmp_path / "tools" / "RVC_CLI"
        rvc_dir.mkdir(parents=True)
        (rvc_dir / "rvc.py").write_text("# stub")

        import subprocess

        def fake_run(*a, **kw):
            raise subprocess.CalledProcessError(
                returncode=1, cmd="rvc", output="fail", stderr="error"
            )

        monkeypatch.setattr("subprocess.run", fake_run)

        with pytest.raises(RVCPipelineError, match="CLI завершился с кодом"):
            proc.run_inference_via_cli(
                "/tmp/in.wav", "/tmp/out.wav", "model", rvc_cli_dir=str(rvc_dir)
            )


class TestXTTSWithRVCPipeline:
    def test_no_rvc_model_returns_xtts_direct(self, tmp_path):
        proc = RVCPostProcessor(models_dir=str(tmp_path))
        pipeline = XTTSWithRVCPipeline(rvc_processor=proc)

        mock_xtts = MagicMock(return_value="/tmp/out.wav")

        result = pipeline.generate_and_enhance(
            text="hello",
            language="en",
            speaker_wav="/tmp/ref.wav",
            output_path="/tmp/out.wav",
            xtts_generator_func=mock_xtts,
            rvc_model=None,
        )

        assert result == "/tmp/out.wav"
        assert mock_xtts.called

    def test_with_rvc(self, tmp_path, monkeypatch):
        proc = RVCPostProcessor(models_dir=str(tmp_path))
        # мок run_inference_via_lib
        monkeypatch.setattr(proc, "run_inference_via_lib", lambda **kw: kw["output_path"])

        pipeline = XTTSWithRVCPipeline(rvc_processor=proc)

        def mock_xtts(text, language, speaker_wav, output_path):
            Path(output_path).write_text("xtts output")
            return output_path

        output = tmp_path / "final.wav"
        result = pipeline.generate_and_enhance(
            text="hello",
            language="en",
            speaker_wav="/tmp/ref.wav",
            output_path=str(output),
            xtts_generator_func=mock_xtts,
            rvc_model="mymodel",
            rvc_settings={"index_rate": 0.8},
        )

        assert result == str(output)
        # временный файл должен быть удалён
        temp = tmp_path / "final_temp_xtts.wav"
        assert not temp.exists()

    def test_xtts_fails_no_output(self, tmp_path, monkeypatch):
        proc = RVCPostProcessor(models_dir=str(tmp_path))
        monkeypatch.setattr(proc, "run_inference_via_lib", lambda **kw: kw["output_path"])

        pipeline = XTTSWithRVCPipeline(rvc_processor=proc)

        def mock_xtts_fail(*a, **kw):
            # не создаёт файл
            return kw.get("output_path", "/tmp/out.wav")

        # удаляем файл если создался случайно
        output = tmp_path / "out.wav"
        if output.exists():
            output.unlink()

        # в generate_and_enhance проверяется существование temp файла после xtts
        # если mock не создаёт файл, должен кинуть RVCPipelineError
        def mock_xtts_no_file(text, language, speaker_wav, output_path):
            # не создаёт файл
            return output_path

        with pytest.raises(RVCPipelineError, match="base generation failed"):
            pipeline.generate_and_enhance(
                text="hello",
                language="en",
                speaker_wav="/tmp/ref.wav",
                output_path=str(output),
                xtts_generator_func=mock_xtts_no_file,
                rvc_model="model",
            )
