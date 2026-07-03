# -*- coding: utf-8 -*-
"""engine/gui/updates.py — проверка и установка обновлений (GUI-обвязка)
(перенесено из gui.py: _do_update, check_and_update, _auto_check_update)."""
import threading

from i18n import t

from engine.gui.statusbar import set_status, set_progress

# Внедряется из main_window: root
root = None


def init(**deps):
    """Внедрение зависимостей из engine.gui.main_window (имена совпадают с
    именами глобальных переменных исходного gui.py)."""
    globals().update(deps)


def _do_update(result):
    """Скачивает и устанавливает обновление."""
    from engine.updater import apply_update, restart
    import tkinter.messagebox as mb
    set_status(t("status_update_download"))
    def _apply():
        ok = apply_update(result["files"], progress_callback=lambda i, t_val: set_progress(int(i / t_val * 100)))
        if ok:
            changelog = result.get("changelog", "").strip()
            msg = t("update_installed", result['remote'])
            if changelog:
                msg += t("update_changelog", changelog)
            msg += t("update_restart")
            def _notify_and_restart():
                mb.showinfo(t("update_done_title"), msg)
                restart()
            root.after(0, _notify_and_restart)
        else:
            root.after(0, lambda: mb.showwarning(t("update_partial_title"), t("update_partial")))
            set_status(t("status_waiting"))
    threading.Thread(target=_apply, daemon=True).start()
def check_and_update():
    """Ручная проверка (по кнопке)."""
    from engine.updater import check_update
    import tkinter.messagebox as mb
    set_status(t("status_update_check"))
    def _run():
        result = check_update()
        if result.get("error"):
            root.after(0, lambda: mb.showerror(t("update_error_title"), result["error"]))
            set_status(t("status_waiting"))
            return
        if not result["available"]:
            root.after(0, lambda: mb.showinfo(t("update_no_title"),
                                               t("update_no_updates", result['local'])))
            set_status(t("status_waiting"))
            return
        def ask():
            changelog = result.get("changelog", "").strip()
            text = t("update_available", result['remote'], result['local'])
            if changelog:
                text += t("update_whats_new", changelog)
            text += t("update_confirm")
            confirmed = mb.askyesno(t("update_title"), text)
            if confirmed:
                _do_update(result)
            else:
                set_status(t("status_waiting"))
        root.after(0, ask)
    threading.Thread(target=_run, daemon=True).start()


def _auto_check_update():
    from engine.updater import check_update
    result = check_update()
    if result.get("error"):
        return
    if result.get("available"):
        def _notify():
            import tkinter.messagebox as mb
            changelog = result.get("changelog", "").strip()
            text = t("update_available", result['remote'], result['local'])
            if changelog:
                text += t("update_whats_new", changelog)
            text += t("update_confirm")
            if mb.askyesno(t("update_title"), text):
                _do_update(result)
        root.after(0, _notify)
