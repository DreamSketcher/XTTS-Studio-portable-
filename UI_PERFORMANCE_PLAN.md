# XTTS Studio UI Performance Map

Baseline after optimization phases 1–4, generated 2026-07-15.

## Static hot-path counts

| Pattern | Count | Risk |
|---|---:|---|
| `after(...)` | 137 | timer duplication, polling and worker/Tk crossings |
| `after_idle(...)` | 3 | preferred coalescing mechanism; currently underused |
| direct `update()` | 0 | nested event loops eliminated from GUI modules |
| `update_idletasks()` | 34 | synchronous layout stalls; review individually |
| `threading.Thread` | 25 | every completion/progress path must use a UI bridge |
| `<Configure>` bindings | 16 | resize storms; require size threshold/debounce |

Counts exclude business/core modules and dictionary `.update()` calls.

## Priority groups

### P0 — thread safety and event pressure

- `env_settings.py`: installer/recovery workers still call `self.after()` from workers.
- `batch_window.py`: task polling and worker status delivery.
- `history_window.py` / `output_window.py`: waveform worker completion.
- AI chat generation/settings workers.
- console stdout/stderr flood — converted to batch queue pump.

### P1 — high-frequency UI work

- chat input resize/token/placeholder work — debounced to 60 ms.
- status/progress updates — deduplicated and progress limited to 12 Hz.
- generation textbox synchronization — unnecessary geometry flushes removed.
- chat smooth-scroll — delayed path no longer forces synchronous layout.
- waveform playback polling: currently 100–200 ms, should share one active-only clock.
- queue polling: currently 500 ms; replace with task-state events.

### P2 — full widget-tree rebuilds

- RVC list: incremental selection and progressive rendering complete; reusable pool pending.
- chat session/messages: append path exists, but session switch still rebuilds all bubbles.
- history/output cards: virtualization and lazy waveform pending.
- settings windows: repeated scrollregion updates and recursive wheel binding.

### P3 — visual effects

- header rainbow/neon timers are independent from `AnimationManager`.
- gradient window redraw uses its own 150 ms timer.
- neon widgets own timers and should be registered with global motion profiles.
- tooltip/hover timers need a shared controller.

## Non-negotiable invariants

- Changes stay in UI infrastructure and `engine/gui/**`; core XTTS/RVC/AI behavior is unchanged.
- No Tk operation from a worker thread.
- No direct `update()` nested event loop.
- No permanent 60 FPS timer while idle.
- Long lists use incremental updates, progressive rendering or recycling.
- Every high-frequency source is rate-limited or event-coalesced.
- Optimization must preserve callback order, persisted settings and user-visible actions.

## Next implementation batches

1. Migrate environment installer/recovery UI delivery to `UIThreadBridge`.
2. Add shared debounced `<Configure>` helper and apply to chat/settings/waveform.
3. Add active-only playback clock for history/output/RVC preview.
4. Introduce reusable recycling list and apply first to history and task queue.
5. Add global motion profile and move rainbow/neon/gradient timers under `AnimationManager`.
6. Add optional performance overlay using animation, bridge and render snapshots.
