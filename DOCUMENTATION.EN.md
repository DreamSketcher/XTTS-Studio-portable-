# 📖 XTTS Studio — Documentation

**[English](./DOCUMENTATION.EN.md)** · **[Русский](./DOCUMENTATION.RU.md)**

Technical reference: architecture, features, data, and project tree.

> Quick overview: **[README.EN.md](./README.EN.md)** · **[README.RU.md](./README.RU.md)**  
> API reference: **[unified_function_reference.EN.md](./unified_function_reference.EN.md)** · **[RU](./unified_function_reference.RU.md)**

---

## Table of contents

1. [About](#about)
2. [Quick start](#quick-start)
3. [Pipeline](#pipeline)
4. [Features (detailed)](#features-detailed)
5. [RVC voice enhancement](#rvc-voice-enhancement)
6. [TTS core (`engine/tts/`)](#tts-core-enginettss)
7. [AI module](#ai-module)
8. [Pronunciation dictionary](#pronunciation-dictionary)
9. [Diagnostics and self-healing](#diagnostics-and-self-healing)
10. [Update system](#update-system)
11. [Requirements](#requirements)
12. [Data and config files](#data-and-config-files)
13. [Project structure](#project-structure)
14. [engine/ modules by area](#engine-modules-by-area)
15. [Development](#development)
16. [Third-party components / licenses](#third-party-components--licenses)

---

## About

**XTTS Studio** is a portable, fully offline text-to-speech and voice-cloning application built on **XTTS v2**.

- Entry point: `XTTS Studio.exe` → BAT → `python\runtime\python.exe` → `gui.py`
- Dependencies: `python\xtts_env`
- Architecture: thin entry · core in `engine/` (no GUI) · UI in `engine/gui/`

The optional **AI module** supports cloud OpenAI-compatible providers and/or **local LLMs** (no keys, offline).

---

## Quick start

1. Download and unpack the archive  
2. **Do not** use a path containing Cyrillic characters  
3. Run `XTTS Studio.exe`  
4. Select a reference clip (~10–20 s)  
5. Enter text  
6. Click **🚀 GENERATE**  
7. Result → `outputs/` (or **🎵 Audio**)

```text
✔  C:\XTTS\
✘  C:\Новая папка\XTTS\
```

---

## Pipeline

```text
Reference → auto-processing → voice library (+ embedding cache)
   ↓
Text → (optional GPT improve on raw text) → normalize → word replacer
   ↓
(optional) AI Conductor rewrite / per-chunk map
   ↓
Chunker (SBD / initials / merge-split) → (optional) prosody / smart pauses*
   ↓
For each chunk:
   · XTTS inference (QC retries when QC is enabled)
   · (optional) RVCPostProcessor on the chunk WAV
   · chunk cache key includes RVC settings
   ↓
Merge + pauses → loudness normalize → de-esser → WAV / MP3
```

\* Smart pauses / prosody are **skipped** when AI Conductor is active (pauses come from `conductor_map`).

**Important:** RVC runs **for every chunk** after XTTS, not only on the final file. The de-esser runs once on the **merged** export.

---

## Features (detailed)

### Synthesis and cloning

- Fully offline TTS  
- Portable folder layout  
- Voice cloning from a short reference  
- Voice library + embedding cache  
- No hard text-length limit  
- RU/EN content  
- **CUDA on demand**: CPU by default; **⚙ Settings → Acceleration**  

### Interface

- **⚙ Settings**: updates · CPU/GPU acceleration · diagnostics  
- Dark/light themes + constructor; immersive titlebar  
- Layout, dock panels, auto-save  
- **RU / EN** UI  
- Input font size and neon glow  
- Auto-update: SHA256, backup, rollback  

### Text

| Module | API | Notes |
|--------|-----|-------|
| `normalizer.py` | `TextNormalizer.normalize`, `safe_character_filter` | Numbers→words, ordinals, time, abbreviations, **ё restoration** |
| `word_replacer.py` | `WordReplacer.apply`, `add_rule`, `remove_rule` | **builtin → auto → ai_corrected → custom**; JSON-only; backups ≤30 |
| `chunker.py` | `TextChunker.chunk_text` | max 175 / target 150 / min 50; initials-aware SBD |
| `prosody_layer.py` | `ProsodyLayer.process` | Semantic pauses; **off with Conductor** |
| `smart_pauses.py` | `SmartPauseEngine.get_pause_ms` | Merge pauses; **off with Conductor** |

### Quality

- 4 presets; sticky tabs **RVC · Trim · Output · XTTS**  
- `quality_settings_last_tab` in `settings.json`  
- Integrated RVC model browser: **Curated · New · Top**, live search, preview before/after download, and cache cleanup  
- Parameter RVC preview: current **Index · Pitch shift · f0** applied to a short segment of the selected voice reference  
- QC, de-esser (on merge), trim, chunk cache (key includes RVC)  

**Persistence (verified):** `settings_ui.save_settings()` writes the complete `quality_params` tree, including `rvc_*`, with **read-modify-write**. Real sessions store `rvc_enable`, `rvc_model`, `rvc_index_rate`, `rvc_pitch_shift`, and `rvc_f0_method`.

### Other

Task queue, batch TXT, history, chunk highlighting, statistics, WAV/MP3.

---

## RVC voice enhancement

Optional **Retrieval-based Voice Conversion** stage after XTTS. The feature is split into **setup** (portable install), **catalog/parser/cache** (model discovery and lifecycle), **pipeline** (inference), and the **GUI model browser + shared audio player**.

### User workflow

1. Open a quality preset and select the **RVC** tab.
2. Enable **RVC post-processing**.
3. Open the model browser and choose **★ Curated**, **🆕 New**, **🔥 Top**, or enter a search query.
4. Select a row. Press **▶** to hear a short sample without downloading the checkpoint; press **■** to stop.
5. Press **⬇** for a direct model file, or **🔗** when the source requires a browser/manual download.
6. After download, the model moves to the local list and retains **▶ / ■** preview when source metadata is available.
7. Use **🧹** to clear temporary pre-download previews and interrupted downloads. Samples attached to installed models are preserved until those models are deleted.
8. Select the local model and adjust **Index**, **Pitch**, and **f0 method** for the preset.
9. Press the separate **▶ parameter preview** button immediately to the left of the model selector. XTTS Studio applies the current settings to the first six seconds of the selected voice reference in a background RVC pass, caches the result, and plays it; **■** stops playback.

### Where RVC is called (generation)

In `engine/tts/__init__.py` → `run_tts()`:

1. Pop `rvc_enable`, `rvc_model`, `rvc_index_rate`, `rvc_pitch_shift`, `rvc_f0_method` from the preset so they never reach XTTS `inference()`.
2. Include those values in the **chunk cache key** (`_rvc_*` fields) so cache does not mix “same text / different RVC”.
3. After XTTS writes the chunk WAV (and QC accepts it), if `rvc_enable and rvc_model`:
   - `get_rvc_processor()` → lazy singleton `RVCPostProcessor`
   - `run_inference_via_lib(chunk_path, chunk_path, model_name=..., ...)` (in-place convert)
4. On `RVCPipelineError` / unexpected error: **log and keep the XTTS chunk** (generation does not abort).

Facade: `engine/tts_runner.py` re-exports `run_tts`, `get_tts`, `detect_device`, `word_replacer` from `engine.tts`.

GUI entry: `engine/gui/generation.py` → `generate()` builds a `Task` with `quality_params={**preset vars including rvc_*}`, queues via `task_manager`.

### Pipeline classes (`engine/rvc_pipeline.py`)

| Name | Role |
|------|------|
| `RVCPipelineError` | Raised on missing model / API mismatch / failed infer |
| `RVCPostProcessor` | Loads `.pth` (+ optional `.index`), runs `rvc-python` |
| `XTTSWithRVCPipeline` | XTTS → temp WAV → RVC → final path; skips RVC if no model |

**`RVCPostProcessor.run_inference_via_lib(...)`** (production path):

1. Lazy-import `rvc_python.infer.RVCInference`  
2. `load_model(model_path, version="v2", index_path=...)`  
3. `set_params(f0up_key=pitch_shift, f0method=..., index_rate=..., filter_radius=3, resample_sr=0, rms_mix_rate=0.25, protect=0.33)`  
4. `infer_file(input_path, output_path)` — **exactly two arguments** (pitch is **not** passed here)

Device strings are normalized to `cpu:0` / `cuda:0`.  
Optional CLI path: `run_inference_via_cli` (`tools/RVC_CLI` / global `rvc`).

**Runtime reporting and model validation**

- One concise start line reports model, CPU/CUDA device, index ratio, pitch, and f0 method.
- One completion line reports the output filename.
- Direct `print()` noise and INFO messages from `rvc-python` / `fairseq` are scoped out during inference; warnings/errors still become `RVCPipelineError` where applicable.
- Before inference, `_validate_rvc_checkpoint` rejects empty checkpoints and HTML/XML responses accidentally stored with a `.pth` extension.
- CLI stderr/stdout is compacted to the last useful non-noise lines when a subprocess fails.

### Catalog, site parsing, previews, and cache (`engine/rvc_catalog.py`)

The RVC catalog has three user-facing sources. All sources are normalized to the same entry format, so download, preview, page opening, and local metadata use one code path.

| Catalog | Source | Network behavior |
|---------|--------|------------------|
| **★ Curated** | `json/rvc_catalog_seed.json` or `models/rvc/catalog_cache.json` | Available offline; remote GitHub catalog is queried only when local data is empty or refresh is forced |
| **🆕 New** | First page of the public voice-models.com feed (`fetch_data.php`, empty search) | Loaded on demand; cached in memory for 15 minutes |
| **🔥 Top** | Public `https://voice-models.com/top` table | Parsed on demand; cached in memory for 15 minutes |

#### voice-models.com parsing

The site is treated as a public index, not as a required runtime dependency:

1. `_parse_vm_table(html)` extracts the model page id, title, creator, size, and download link from table rows.
2. `_row_to_entry(row)` normalizes a parsed row to the catalog entry schema.
3. `browse_voice_models("new" | "top")` preserves site order and caches normalized entries.
4. `search_voice_models(query)` uses `fetch_data.php`; autocomplete is a fallback when the table endpoint returns too few rows.
5. `search_catalog(...)` merges local seed/cache matches with live results and removes duplicate ids.
6. Network failures are soft: the UI retains local models and the offline curated catalog.

The parser recognizes direct Hugging Face `/resolve/` links, direct `.pth` / `.zip` files, and Google Drive file links. Folder-only or page-only links remain usable through **🔗 Open page** instead of being presented as direct downloads.

#### Audio preview discovery

A preview does **not** require downloading the RVC checkpoint:

1. `can_preview(entry)` checks a remembered local sample, a direct preview URL, or a voice-models.com model page.
2. `get_preview_url(entry)` lazily requests that model page only after the user presses **▶**.
3. `_PreviewAudioParser` selects the real `<audio id="vm-fit-audio" ...>` source; embedded script audio URLs are a fallback.
4. `get_preview_audio_path(entry)` downloads only the short MP3/WAV/OGG/M4A sample, with a 32 MiB safety limit.
5. The sample is played inside XTTS Studio through the existing pygame player. If pygame is unavailable, `open_preview(entry)` opens the stream in the system browser.

Preview URLs are cached for 24 hours after success. A failed lookup has a short 5-minute cache, so temporarily unavailable pages can be retried later.

#### On-demand parameter preview

The separate button beside the model selector is different from the website sample buttons inside the list. It performs a real local RVC pass with the currently selected downloaded model:

1. The source is the current voice-reference file, not an already converted website preview.
2. At most the first six seconds are copied to a temporary WAV.
3. Current `rvc_index_rate`, `rvc_pitch_shift`, and `rvc_f0_method` are applied in a background worker through `get_rvc_processor()`.
4. The cache fingerprint includes reference path/size/mtime, model path/size/mtime, optional `.index` size/mtime, and all three parameters.
5. An identical request reuses the WAV in `.parameter_preview_cache` immediately; each model keeps up to six recent variants.
6. **▶** renders or plays; **■** stops through the shared pygame player. If parameters change during rendering, the stale result is cached but not auto-played.

`Index` changes the audio only when a matching `.index` file exists. Pitch shift and f0 method still apply to models without an index.

#### Local model metadata

Models downloaded through the catalog receive a sidecar file:

```text
models/rvc/.metadata/<local_model_name>.json
```

The sidecar stores the catalog id, display name, author, source/page URL, local filename, preview URL, and cached preview path. This allows a downloaded local model to keep its **▶ / ■** preview action after it disappears from the remote results list.

`get_local_model_entry(name)` also migrates older downloads when it can match their filename to:

- the offline seed or disk catalog cache;
- a loaded **New** / **Top** catalog;
- a live search result seen in the current session.

A manually copied `.pth` has no embedded demo audio. If no catalog/page metadata can be matched, the model remains fully usable for conversion but no preview button is shown.

#### Preview and partial-download cache lifecycle

| Path / pattern | Purpose | Cleanup behavior |
|----------------|---------|------------------|
| `models/rvc/.preview_cache/` | Short website samples used by list-row ▶ preview | Orphan/pre-download samples can be cleared; samples referenced by installed-model metadata are protected |
| `models/rvc/.parameter_preview_cache/<model>/` | Locally rendered Index/Pitch/f0 preview WAVs | Kept while the model is installed; incomplete `.part` files and orphan model folders are cleared; the whole folder is removed with the model |
| `models/rvc/.metadata/*.json` | Source and preview metadata for installed models | Kept by cache cleanup; removed with the corresponding model |
| `models/rvc/*.part`, `*.part.*`, `*.partial`, `*.tmp`, `*.download`, `*.crdownload` | Interrupted model downloads / temporary files | Removed by **🧹 Clear RVC cache** |
| `models/rvc/catalog_cache.json` | Disk catalog cache | Not removed by RVC preview/partial cleanup |
| `models/rvc/*.pth`, `*.index` | Installed model weights and optional index | Never removed by cache cleanup |

`clear_rvc_cache()` returns counts and released bytes. It removes orphan website samples, interrupted-download files, unfinished parameter-preview `.part` files, orphan parameter-preview folders, and abandoned metadata `.tmp` files. Website samples and completed parameter previews for installed models are kept until `delete_local_model(name)`; shared samples still referenced by another installed model are retained.

#### Public API

| Function | Description |
|----------|-------------|
| `get_catalog(force_refresh=False)` | Disk cache/seed first; GitHub raw catalog only if empty or forced; one attempt and 6-hour failure cooldown |
| `browse_voice_models(mode, max_results=50, force_refresh=False)` | Parse public **New** or **Top** catalogs and keep a 15-minute in-memory cache |
| `search_catalog(query, max_results=30, live=True)` | Local seed/cache match followed by optional live search, with id deduplication |
| `search_voice_models(query, ...)` | voice-models.com table search plus autocomplete fallback; fails soft |
| `can_preview(entry)` / `get_preview_url(entry)` | Detect and lazily resolve a model-page audio sample |
| `get_preview_audio_path(entry, force_refresh=False)` | Download/reuse a short website sample in `.preview_cache` |
| `get_parameter_preview_cache_path(model_name, fingerprint)` | Return/create the per-model cache path for a locally rendered parameter preview |
| `prune_parameter_preview_cache(model_name, keep=6)` | Limit cached Index/Pitch/f0 variants for one installed model |
| `open_preview(entry)` | Browser fallback for website-sample playback |
| `download_model(entry, progress_callback, cancelled_flag)` | HF `/resolve/`, direct zip/pth, best-effort Google Drive file; zip → largest `.pth` + best `.index`; writes local metadata |
| `get_local_model_entry(name)` | Restore preview/source metadata for a downloaded model, including legacy matching |
| `clear_rvc_cache()` | Remove orphan preview and interrupted-download cache while preserving installed models and their samples |
| `is_downloaded` / `local_model_path` / `delete_local_model` | Local lifecycle helpers; `.pth` is canonical, and delete also handles `.index`, metadata, and the protected sample |
| `open_model_page(entry)` | Open a non-direct model/folder page in the browser |

Catalog entry **must** have `id`, `name`, `url`. Optional fields include `filename`, `author`, `license`, `description`, `source`, `page_url`, `size`, `sha256`, `downloadable`, `catalog`, `preview_url`, `preview_cache_path`, and `local_name`.

### Install stack (`engine/env_core/rvc_setup.py`)

| Function | Description |
|----------|-------------|
| `rvc_status()` | Subprocess probe: can import `RVCInference`? |
| `install_rvc(progress_cb=None)` | Install into portable `python/xtts_env/Lib/site-packages` |
| `uninstall_rvc(progress_cb=None)` | Remove rvc_python + fairseq tails (keeps shared packages like `portalocker`) |
| `detect_torch_build(site_packages)` | Same torch variant as base install (`cu118` / `cpu`) |

**Install highlights (Windows-safe)**

- Prebuilt **fairseq** wheels by CPython version (avoids MSVC compile)  
- `rvc-python --no-deps`, then real deps from package METADATA  
- Dynamic constraints so existing **torch+cu118/cpu** is not re-downloaded (~GB)  
- Retry without `--upgrade` on WinError 5 (locked `.pyd` while app is running)  
- Auto-heal missing modules after install (import probe loop)  
- PyYAML force-reinstall (common breakage with `--target` installs)  

### GUI model browser (`engine/gui/rvc_model_dropdown.py`)

`RVCModelDropdown` is a custom model browser embedded in each preset's RVC tab.

**Persistent controls**

- Trigger button: current local model + **▾**.
- Search field: debounced local results first, live voice-models.com results second.
- Catalog bar: **★ Curated · 🆕 New · 🔥 Top**. Selecting a catalog clears the current search.
- **🧹 Clear cache**: removes orphan preview samples and interrupted model downloads after confirmation; installed models and their attached samples are preserved.
- The result list is a canvas with a vertical scrollbar and wheel handling.

**Row actions**

| Row type | Actions when selected |
|----------|-----------------------|
| Local model with known preview metadata | **▶ / ■** play/stop preview · **🗑** delete model |
| Local model without preview metadata | **🗑** delete model |
| Remote model with direct file URL | **▶ / ■** preview · **⬇** download; during download **✕** cancels |
| Remote page/folder without a direct file URL | **▶ / ■** preview when available · **🔗** open page |

Only the selected row renders active action buttons. The action column is reserved before the text column, so long model names are clipped instead of pushing controls outside the popup. Re-rendering after selection preserves the list position and keeps the active row visible.

Preview playback is shared with `engine/gui/player.py`: a cached sample is loaded into `pygame.mixer.music`, **▶** changes to **■**, natural completion restores **▶**, and starting the normal reference player stops the RVC preview (and vice versa). The current player volume is reused.

Remote downloads report byte progress through the status bar. Successful downloads select the new local model and keep its page/preview metadata for later playback.

### Preset settings UI (`engine/gui/presets.py`)

Sticky tabs (do not scroll away): **RVC · Trim · Output · XTTS**

- RVC tab: enable, model dropdown, separate **▶ / ■ parameter preview**, index, pitch, f0 method  
- Parameter preview uses the active voice reference, runs asynchronously, and reuses the per-model cache for identical settings  
- Output tab: export format, **de-esser**, QC  
- Last tab stored as `quality_settings_last_tab` in `settings.json`  
- Closing the window (button or ✕) calls `save_settings` so **RVC fields persist** inside `quality_params[preset]`  

Preset keys:

```text
rvc_enable, rvc_model, rvc_index_rate, rvc_pitch_shift, rvc_f0_method
```

Plus window-level: `quality_settings_last_tab` ∈ `rvc | trim | out | xtts`.

---

## TTS core (`engine/tts/`)

| Symbol | File | Role |
|--------|------|------|
| `run_tts(...)` | `tts/__init__.py` | Full job |
| `get_tts()` / `get_rvc_processor()` | `tts/__init__.py` | Lazy singletons |
| `tts_runner.py` | project root | Re-export |
| QC helpers | `tts/qc.py` | Repeats, duration, trim, loudness |
| `export_audio` | `tts/export.py` | Merge + de-esser + WAV/MP3 |
| `DeEsser` / `create_de_esser` | `engine/de_esser.py` | 4–9 kHz split-band |

QC performs up to **3** attempts when `qc_enabled`. The de-esser runs in `export_audio` when `de_esser_intensity > 0`.

---

## AI module

### Conductor — `ai_conductor.py`

`conduct(...)` → list / `{rewritten_text, chunks}` / None / fallback.  
Ranges: temperature 0.50–0.90, top_p 0.70–0.95, speed 0.75–1.25, pause 0–1200.  
`rewritten_text` is used only when `rewrite_enabled=True`. Transport: `_call_with_chain`.

### GPT client — `gpt_client.py`

`gpt_settings.json`. Chain: **active → built-ins with a key → custom**.  
`_call_with_chain`, `chat`, `improve_for_tts`, key library, `get_chain_diagnostics`.  
Exceptions: `AIUnavailable`, rate-limit / network errors.

### Local LLM — `local_llm_client.py`

In-process GGUF (`llama-cpp-python`). HF catalog, download+resume, `call_local_llm` (CPU max_tokens ≤256). GPU→CPU fallback + broken-backend tracking.

### `gui.py`

Single instance, `_ensure_dependencies_before_startup`, recovery UI, `main` + `updater.check_startup_health`.  
`llama_cpp` / `rvc_python` are **not** critical.

---

## Pronunciation dictionary

`WordReplacer`. Source of truth: `word_rules.json`.  
Priority: **builtin → auto → ai_corrected → custom**.  
Backups ≤30. UI: **📖 Dictionary**. Conductor can write `ai_corrected` entries.

---

## Diagnostics and self-healing

Package: **`engine/env_core/`** (re-export in `__init__.py`, facade `env_setup`).

| Module | Main responsibility |
|--------|---------------------|
| `cpu_gpu.py` | `detect_cpu`, `detect_gpu` |
| `diagnostics.py` | `run_full_diagnostics` (isolated process), `get_broken_critical`, `scan_for_garbage` + quarantine, `run_error_recovery`; CRITICAL vs OPTIONAL=`{llama_cpp,rvc_python}` |
| `torch_setup.py` | `install_torch` / `torch_status` / cu118\|cpu variant |
| `llama_setup.py` | cuda/vulkan/cpu, broken backends, smoke test |
| `rvc_setup.py` | RVC install/probe |

Startup: `gui.py` → full diagnostics → recovery only for critical components.

---

## Update system

**`engine/updater.py`** (not an `Updater` class).

| Function | Description |
|----------|-------------|
| `check_update()` | Version comparison + files + sha256 + manual reinstall |
| `apply_update(...)` | staging → verify → backup → live → removed_files → marker |
| `check_startup_health()` | `ok` / `first_attempt` / `rolled_back` |
| `confirm_update_success()` | Called after successful GUI startup |
| `rollback_update()` / `restart()` | Rollback / restart |

Cancellation works before live-file replacement. When `local < min_app_version`, a full reinstall is required.

---

## Requirements

| | CPU | CUDA |
|---|---|---|
| OS | Windows 10/11 x64 | same |
| RAM | 8+ GB | 8+ GB |
| GPU | — | NVIDIA, 4+ GB VRAM, CC 6.0+ |

---

## Data and config files

| File | Purpose |
|------|---------|
| `settings.json` | session, `quality_params` (including **rvc_***), `quality_settings_last_tab`, theme, language |
| `gpt_settings.json` | AI providers, keys, models |
| `word_rules.json` | dictionary |
| `word_rules_backups/` | dictionary backups |
| `chat_history.json` / `history.json` | chat / generations (history max 100) |
| `version.json` / `checksums.txt` | updates |
| `json/rvc_catalog_seed.json` | offline **★ Curated** catalog |
| `models/rvc/*.pth`, `*.index` | installed RVC weights and optional feature index |
| `models/rvc/catalog_cache.json` | disk catalog cache |
| `models/rvc/.preview_cache/` | short website samples for list-row ▶ preview |
| `models/rvc/.parameter_preview_cache/<model>/` | locally rendered previews of current Index/Pitch/f0 on the voice reference |
| `models/rvc/.metadata/*.json` | source/page/preview metadata for downloaded local models |
| `.llama_broken_backends.json` / `.known_safe_files.json` | backend / diagnostics |

---

## Project structure

**Entry point:** `XTTS Studio.exe` → BAT → `python\runtime\python.exe` → `gui.py` → `python\xtts_env`

```text
XTTS Studio (portable)
│
├── gui.py                        ← entry point: launches the interface only
├── i18n.py                       ← UI localization (RU / EN)
├── settings.json                 ← session settings (auto)
├── gpt_settings.json             ← AI provider, keys, models (auto)
├── word_rules.json               ← pronunciation dictionary
├── chat_history.json             ← AI chat session history
├── history.json                  ← generation history
├── version.json                  ← version and update-system data
├── env_cache.cfg                 ← environment-scan cache
├── generate_version_manifest.py  ← generates version manifest for updates
├── theme_settings.json           ← user theme/color scheme
├── checksums.txt                 ← SHA256 for update verification
├── .llama_broken_backends.json   ← broken llama.cpp backends (auto)
│
├── engine/                       ═══ TECHNICAL CORE (no tkinter) ═══
│   │
│   │   ── generation pipeline ──
│   ├── tts_runner.py
│   ├── chunker.py
│   ├── normalizer.py
│   ├── word_replacer.py
│   ├── text_utils.py
│   ├── smart_pauses.py
│   ├── prosody_layer.py
│   ├── de_esser.py
│   ├── rvc_pipeline.py           ← RVC post-process (rvc-python)
│   ├── rvc_catalog.py            ← RVC parsing / browse / preview / download / cache
│   │
│   │   ── AI module ──
│   ├── ai_conductor.py
│   ├── chat_window.py
│   ├── gpt_client.py
│   ├── local_llm_client.py
│   ├── env_setup.py
│   │
│   │   ── voice and audio ──
│   ├── reference_processor.py
│   ├── voice_manager.py
│   ├── audio_backend.py
│   │
│   │   ── infrastructure ──
│   ├── task_manager.py
│   ├── task_models.py
│   ├── batch_window.py
│   ├── updater.py
│   ├── paths.py
│   ├── settings_store.py
│   ├── history_store.py
│   ├── output_naming.py
│   ├── text_tools.py
│   └── logging_utils.py
│
│   ├── tts/
│   │   ├── __init__.py           ← generation core
│   │   ├── cache.py
│   │   ├── device.py
│   │   ├── export.py
│   │   ├── qc.py
│   │   └── utils.py
│   │
│   └── gui/                      ═══ INTERFACE (tkinter / customtkinter) ═══
│       ├── main_window.py
│       ├── layout.py
│       ├── theme.py
│       ├── theme_manager.py
│       ├── colors.py
│       ├── widgets.py
│       ├── tooltip.py
│       ├── gradient.py
│       ├── neon_widgets.py
│       ├── helpers.py
│       ├── header_panel.py
│       ├── voice_panel.py
│       ├── player.py             ← reference + RVC preview shared pygame player
│       ├── queue_panel.py
│       ├── batch_panel.py
│       ├── chat_panel.py
│       ├── word_replacer_panel.py
│       ├── console.py
│       ├── textbox.py
│       ├── toolbar.py
│       ├── statusbar.py
│       ├── generation.py
│       ├── presets.py            ← quality presets + parameter-preview button
│       ├── rvc_model_dropdown.py ← RVC browse / search / preview / cache UI
│       ├── settings_ui.py
│       ├── styles_menu.py
│       ├── updates.py
│       ├── chat_window.py
│       ├── ai_conductor.py
│       ├── ai_status_window.py
│       ├── history_window.py
│       ├── output_window.py
│       ├── batch_window.py
│       ├── word_replacer_window.py
│       ├── dialogs.py
│       └── chat_window/          ═══ modular AI chat ═══
│           ├── ...
│           └── engine/
│
├── json/
│   └── rvc_catalog_seed.json     ← offline RVC seed catalog
│
├── models/
│   ├── xtts_v2/                  ← XTTS model (offline)
│   └── rvc/
│       ├── *.pth / *.index       ← installed RVC models
│       ├── catalog_cache.json    ← disk catalog cache
│       ├── .preview_cache/       ← short website ▶ samples
│       ├── .parameter_preview_cache/ ← local Index/Pitch/f0 preview WAVs
│       └── .metadata/            ← source/preview sidecars for local models
├── library/<voice_name>/         ← voice profiles + embedding cache
├── outputs/_cache/               ← finished files + chunk cache
├── logs/
├── reference/
├── word_rules_backups/
├── test/                         ← pytest
├── tools/
├── ffmpeg/bin/
└── python/
    ├── xtts_env/
    └── runtime/                  ← Python 3.11 portable
```

> `engine/gui/chat_window.py` assembles the chat UI; `engine/gui/chat_window/` holds submodules and nested `engine/` for generation/sessions.

---

## engine/ modules by area

### Generation pipeline

- `tts_runner` (facade) · `tts/*` · `chunker` · `normalizer` · `word_replacer` · `smart_pauses` / `prosody_layer` (off with Conductor) · `de_esser`.
- **`rvc_pipeline.py`** — `RVCPostProcessor` / `XTTSWithRVCPipeline` through `rvc-python`.
- **`rvc_catalog.py`** — Curated/New/Top parsing, live search, website preview, parameter-preview cache, metadata, model downloads, and protected cache cleanup.
- **`gui/rvc_model_dropdown.py`** — catalog tabs, search, selected-row actions, preview/download/delete, and the 🧹 button.
- **`gui/presets.py`** — separate ▶ / ■ button for a real preview of current Index/Pitch/f0 on the voice reference.
- **`gui/player.py`** — shared pygame transport for the voice reference and RVC preview.
- **`env_core/rvc_setup.py`** — portable RVC install, uninstall, and probe.

### AI

`ai_conductor` · `gpt_client` · `local_llm_client` · chat UI

### Voice

`reference_processor` (trim + SNR) · `voice_manager` · `de_esser`

### Infrastructure

`task_manager` · `history_store` · `updater` · `settings_ui` · `env_core/*`.  
`i18n.py` contains RU/EN keys for catalogs, preview/playback, parameter preview, and RVC cache cleanup.

---

## Development

AI-assisted tooling; pytest in `test/`; utilities in `tools/`.  
Architecture and UI polish — with Arena.ai Agent Mode and Claude.

Tests: **pytest** in `test/` (`RUN_TESTS.bat`)

platform win32 -- Python 3.11.7, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\XTTS Studio
configfile: pyproject.toml
plugins: timeout-2.4.0
timeout: 60.0s
timeout method: thread
timeout func_only: False
collected 621 items / 2 skipped

---

## Third-party components / licenses

- **XTTS v2** (Coqui) — [CPML](https://coqui.ai/cpml)  
- Project license: [LICENSE.md](./LICENSE.md)  
- Community RVC models remain under their own licenses  

---

## Support

**BTC:** `bc1qz78u3lvagt3v886359glv57ct6rnlh506wjmdy`

---

**XTTS Studio** · by EXIZ10TION · [README EN](./README.EN.md) · [README RU](./README.RU.md) · [RU docs](./DOCUMENTATION.RU.md) · [License](./LICENSE.md)
