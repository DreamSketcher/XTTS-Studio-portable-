"""Global visual-motion quality policy; never changes application logic."""

import os

_VALID = {"ultra", "balanced", "performance", "reduced", "off"}
_cached = None
_adaptive_degraded = False


def get_motion_profile() -> str:
    global _cached
    if _cached in _VALID:
        return _cached
    env = os.environ.get("XTTS_UI_MOTION", "").strip().lower()
    if env in _VALID:
        _cached = env
        return env
    try:
        from engine.settings_store import load_settings

        value = str(load_settings().get("ui_motion_profile", "balanced")).lower()
    except Exception:
        value = "balanced"
    _cached = value if value in _VALID else "balanced"
    return _cached


def set_motion_profile(profile: str) -> None:
    global _cached
    value = str(profile or "").lower()
    if value not in _VALID:
        raise ValueError(f"unknown motion profile: {profile}")
    _cached = value


def set_adaptive_degraded(degraded: bool) -> None:
    global _adaptive_degraded
    _adaptive_degraded = bool(degraded)


def get_effective_motion_profile() -> str:
    profile = get_motion_profile()
    # Ultra is an explicit opt-in and is never auto-downgraded. Balanced may
    # temporarily shed decorative work when measured frame times are poor.
    if _adaptive_degraded and profile == "balanced":
        return "adaptive"
    return profile


def decorative_effects_enabled() -> bool:
    return get_effective_motion_profile() not in ("performance", "reduced", "off")


def transitions_enabled() -> bool:
    return get_effective_motion_profile() != "off"


def adjusted_interval(base_ms: int) -> int:
    profile = get_effective_motion_profile()
    factor = {
        "ultra": 1.0,
        "balanced": 1.35,
        "performance": 2.0,
        "adaptive": 2.5,
        "reduced": 3.0,
        "off": 1000.0,
    }[profile]
    return max(16, min(2000, round(max(1, base_ms) * factor)))
