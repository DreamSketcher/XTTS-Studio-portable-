from __future__ import annotations
import tkinter as tk
from tkinter import colorchooser, ttk, messagebox
import engine.gui.chat_window.state as state
from engine.gui.chat_window.custom_widgets import TkFrame, TkLabel, TkButton
from engine.gui.chat_window.ui_utils import _make_button, _set_dark_titlebar
from engine.gui.theme_manager import load_theme, save_theme, get_layout_preset
from engine.gui.colors import Colors
from i18n import t

# ПРИМЕЧАНИЕ (фикс): custom_widgets.py не экспортирует функцию "_c" —
# её здесь никогда не было (ImportError на реальной машине пользователя
# подтвердил это). Palette-lookup по имени цвета уже реализован во всех
# остальных панелях проекта через engine.gui.colors.Colors (единственный
# источник палитр DARK/LIGHT), поэтому определяем "_c" локально как
# обёртку над Colors — без изменения общего custom_widgets.py.
def _c(name: str) -> str:
    """Возвращает значение цвета по имени атрибута Colors (например
    _c("BG_CARD") -> Colors.BG_CARD). Fallback на белый, если атрибута
    нет — чтобы окно конструктора темы не падало из-за опечатки в имени."""
    return getattr(Colors, name, "#ffffff")


# ── Человекочитаемые русские названия технических ключей цветов ──
# ВРЕМЕННОЕ решение до полноценной интеграции в i18n (t()): сейчас имена
# цветов (BG_MAIN, TEXT_DIM и т.п.) показывались пользователю "как есть" —
# технические константы вместо понятных подписей. Пока полноценные ключи
# перевода не добавлены в i18n, используем локальный RU-словарь с fallback
# на исходное техническое имя (если ключ не найден — ничего не ломается).
COLOR_LABELS_RU = {
    "BG_MAIN": "Фон — основной",
    "BG_SEC": "Фон — вторичный",
    "BG_DARK": "Фон — тёмный",
    "TEXT_MAIN": "Текст — основной",
    "TEXT_DIM": "Текст — приглушённый",
    "ACCENT": "Акцент",
    "ACCENT_HOVER": "Акцент — при наведении",
    "ACCENT_DARK": "Акцент — тёмный",
    "BORDER": "Граница",
    "SUCCESS": "Успех",
    "ERROR": "Ошибка",
}


def _color_label(color_name: str) -> str:
    """Человекочитаемая подпись для технического имени цвета (см.
    COLOR_LABELS_RU выше). Если имя не найдено в словаре — показываем
    исходный технический ключ, чтобы ничего не потерялось."""
    return COLOR_LABELS_RU.get(color_name, color_name)


# ── Fallback-переводы для окна конструктора темы ──
# ВАЖНО: на реальной машине пользователя t() НЕ бросает исключение на
# отсутствующий ключ — она возвращает сам ключ "как есть" (это видно на
# скриншоте: заголовок окна показывал буквально "theme_custom_title" и
# т.п.). Значит, эти ключи просто не добавлены в файлы локализации проекта.
# _tr() ниже — временное решение: пробует t(key), и если результат совпал
# с самим ключом (перевод не найден), подставляет русский текст-заглушку.
# Как только в i18n добавят настоящие переводы для этих ключей — _tr()
# автоматически начнёт возвращать их вместо заглушки, ничего менять не
# придётся.
THEME_UI_FALLBACKS_RU = {
    "theme_custom_title": "Конструктор темы",
    "theme_custom_desc": "Настройте внешний вид и раскладку интерфейса",
    "theme_font_label": "Шрифт интерфейса:",
    "theme_font_size": "Размер шрифта:",
    "theme_padding_label": "Внутренние отступы:",
    "theme_layout_label": "Раскладка интерфейса",
    "theme_layout_classic": "Классическая",
    "theme_layout_compact": "Компактная",
    "theme_layout_wide": "Широкая",
    "theme_reset_btn": "Отмена",
    "theme_save_btn": "Сохранить",
}


def _tr(key: str) -> str:
    """Перевод с fallback на русский текст, если t(key) вернула ключ
    без изменений (перевод отсутствует в i18n) — см. пояснение выше."""
    try:
        value = t(key)
    except Exception:
        value = key
    if value == key:
        return THEME_UI_FALLBACKS_RU.get(key, key)
    return value



def open_theme_customizer(parent, on_layout_changed=None):
    """Открывает окно расширенной настройки темы.

    on_layout_changed: необязательный callback(preset: dict) -> bool,
    вызывается при сохранении для live-применения пресета раскладки ко
    всем панелям (см. main_window.apply_layout_preset_to_all). Если не
    передан или бросает исключение — просто сохраняем в JSON, полное
    применение произойдёт при следующем запуске приложения.
    """
    win = tk.Toplevel(parent)
    _set_dark_titlebar(win)
    win.title(_tr("theme_custom_title"))
    win.geometry("720x800")
    # ИСПРАВЛЕНО: окно теперь можно свободно менять по размеру (раньше
    # фиксированный "700x800" мог обрезать содержимое на маленьких экранах,
    # а скроллить внутри можно было только перетаскиванием узкой полосы
    # прокрутки — колесо мыши не работало вообще, см. _bind_mousewheel ниже).
    win.minsize(560, 480)
    win.resizable(True, True)
    win.configure(bg=_c("BG_DARK"))
    win.transient(parent)
    win.grab_set()

    current_theme = load_theme()
    
    # Главный контейнер
    main = TkFrame(win, bg=_c("BG_DARK"))
    main.pack(fill="both", expand=True, padx=20, pady=20)

    TkLabel(
        main, text=_tr("theme_custom_desc"),
        bg=_c("BG_DARK"), fg=_c("TEXT_MAIN"), font=("Segoe UI", 17, "bold"),
    ).pack(anchor="w", pady=(0, 16))

    # Область прокрутки
    canvas = tk.Canvas(main, bg=_c("BG_DARK"), highlightthickness=0)
    scrollbar = ttk.Scrollbar(main, orient="vertical", command=canvas.yview)
    scroll_frame = TkFrame(canvas, bg=_c("BG_DARK"))

    _scroll_window_id = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")

    def _on_scroll_frame_configure(event=None):
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _on_canvas_configure(event):
        # Растягиваем внутренний scroll_frame по ширине canvas, чтобы дочерние
        # виджеты (fill="x") корректно заполняли всю ширину окна при resize.
        canvas.itemconfig(_scroll_window_id, width=event.width)

    scroll_frame.bind("<Configure>", _on_scroll_frame_configure)
    canvas.bind("<Configure>", _on_canvas_configure)

    canvas.configure(yscrollcommand=scrollbar.set)

    # ИСПРАВЛЕНО: canvas/scrollbar здесь больше НЕ упаковываются — иначе они
    # (fill="both", expand=True) забирали всё свободное место в "main" ДО
    # того, как ниже упаковывалась нижняя панель с кнопками "Сохранить"/
    # "Отмена" — из-за этого кнопки сжимались в узкую полоску в углу окна
    # (см. скриншот пользователя). Правильный порядок: сначала закрепить
    # btn_row снизу (side="bottom"), и только потом отдать canvas/scrollbar
    # оставшееся пространство. Реальный .pack() для canvas/scrollbar теперь
    # вызывается в самом конце функции, после btn_row.pack(side="bottom").

    # ── Прокрутка колесом мыши (раньше отсутствовала полностью) ──
    # Windows/macOS шлют <MouseWheel> с event.delta (обычно ±120 за "щелчок"),
    # Linux (X11) вместо этого шлёт <Button-4>/<Button-5>. Обрабатываем оба
    # варианта. Биндим только пока курсор над окном конструктора темы
    # (bind при Enter/Leave), чтобы не перехватывать скролл всего приложения.
    def _on_mousewheel_windows(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_mousewheel_linux_up(event):
        canvas.yview_scroll(-1, "units")

    def _on_mousewheel_linux_down(event):
        canvas.yview_scroll(1, "units")

    def _bind_mousewheel(event=None):
        canvas.bind_all("<MouseWheel>", _on_mousewheel_windows)
        canvas.bind_all("<Button-4>", _on_mousewheel_linux_up)
        canvas.bind_all("<Button-5>", _on_mousewheel_linux_down)

    def _unbind_mousewheel(event=None):
        canvas.unbind_all("<MouseWheel>")
        canvas.unbind_all("<Button-4>")
        canvas.unbind_all("<Button-5>")

    canvas.bind("<Enter>", _bind_mousewheel)
    canvas.bind("<Leave>", _unbind_mousewheel)
    # На случай закрытия окна с курсором внутри canvas — снимаем глобальный bind,
    # чтобы он не "утёк" в остальной интерфейс после закрытия конструктора темы.
    win.bind("<Destroy>", lambda e: _unbind_mousewheel(), add="+")

    # ── Секция Цветов ─────────────────────────────────────────────────────────
    # Небольшой визуальный апгрейд: тонкая рамка вокруг каждой секции —
    # TkFrame (см. custom_widgets.py) уже умеет принимать highlightthickness/
    # highlightbackground и для обычного tk.Frame (нативная поддержка), и для
    # CTkFrame (конвертируется в border_width/border_color), поэтому это
    # безопасно работает в обоих режимах (CTK_AVAILABLE True/False).
    colors_group = TkFrame(scroll_frame, bg=_c("BG_CARD"), padx=15, pady=15,
                           highlightthickness=1, highlightbackground=_c("BORDER"))
    colors_group.pack(fill="x", pady=(0, 16))
    
    TkLabel(colors_group, text="Цвета интерфейса", bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"), 
            font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 10))

    color_vars = {}

    def pick_color(name, var, btn):
        color = colorchooser.askcolor(initialcolor=var.get())[1]
        if color:
            var.set(color)
            btn.config(bg=color)

    for color_name, color_val in current_theme["colors"].items():
        row = TkFrame(colors_group, bg=_c("BG_CARD"))
        row.pack(fill="x", pady=2)
        
        var = tk.StringVar(value=color_val)
        color_vars[color_name] = var
        
        # Показываем понятную русскую подпись (_color_label), а не сырой
        # технический ключ (BG_MAIN, TEXT_DIM и т.п.) — см. COLOR_LABELS_RU.
        TkLabel(row, text=_color_label(color_name), bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"), 
                font=("Segoe UI", 12), width=24, anchor="w").pack(side="left")
        
        # Кнопка выбора цвета
        btn = TkButton(row, text=" 🎨 ", 
                       bg=color_val, fg="white" if color_val == "#16161e" else "black",
                       width=5, relief="flat", cursor="hand2",
                       command=lambda n=color_name, v=var, b=None: pick_color(n, v, b))
        
        # Замыкаем кнопку в функцию, чтобы она могла менять свой цвет
        btn.config(command=lambda n=color_name, v=var, b=btn: pick_color(n, v, btn))
        btn.pack(side="left", padx=10)

    # ── Секция Шрифтов ──────────────────────────────────────────────────────────
    fonts_group = TkFrame(scroll_frame, bg=_c("BG_CARD"), padx=15, pady=15,
                          highlightthickness=1, highlightbackground=_c("BORDER"))
    fonts_group.pack(fill="x", pady=(0, 16))
    
    TkLabel(fonts_group, text="Типографика", bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"), 
            font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 10))

    font_main_var = tk.StringVar(value=current_theme["fonts"]["main"])
    font_size_var = tk.IntVar(value=current_theme["fonts"]["size_main"])
    
    row_f = TkFrame(fonts_group, bg=_c("BG_CARD"))
    row_f.pack(fill="x")
    
    TkLabel(row_f, text=_tr("theme_font_label"), bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"), font=("Segoe UI", 12)).pack(side="left")
    tk.Entry(row_f, textvariable=font_main_var, bg=_c("BG_INPUT"), fg=_c("TEXT_MAIN"), 
             insertbackground=_c("TEXT_MAIN"), relief="flat", font=("Segoe UI", 12)).pack(side="left", padx=10, ipady=5)

    row_s = TkFrame(fonts_group, bg=_c("BG_CARD"))
    row_s.pack(fill="x", pady=10)
    
    TkLabel(row_s, text=_tr("theme_font_size"), bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"), font=("Segoe UI", 12)).pack(side="left")
    tk.Spinbox(row_s, from_=8, to=24, textvariable=font_size_var, bg=_c("BG_INPUT"), 
               fg=_c("TEXT_MAIN"), insertbackground=_c("TEXT_MAIN"), relief="flat", font=("Segoe UI", 12)).pack(side="left", padx=10)

    # ── Секция Геометрии ──────────────────────────────────────────────────────
    geo_group = TkFrame(scroll_frame, bg=_c("BG_CARD"), padx=15, pady=15,
                        highlightthickness=1, highlightbackground=_c("BORDER"))
    geo_group.pack(fill="x", pady=(0, 16))
    
    TkLabel(geo_group, text="Геометрия и Отступы", bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"), 
            font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 10))

    pad_var = tk.IntVar(value=current_theme["geometry"]["padding_main"])
    row_p = TkFrame(geo_group, bg=_c("BG_CARD"))
    row_p.pack(fill="x")
    
    TkLabel(row_p, text=_tr("theme_padding_label"), bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"), font=("Segoe UI", 12)).pack(side="left")
    tk.Scale(row_p, from_=0, to=40, orient="horizontal", variable=pad_var, 
             bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"), highlightthickness=0, troughcolor=_c("BG_INPUT")).pack(side="left", fill="x", expand=True, padx=10)

    # ── Секция Расположения ────────────────────────────────────────────────────────
    lay_group = TkFrame(scroll_frame, bg=_c("BG_CARD"), padx=15, pady=15,
                        highlightthickness=1, highlightbackground=_c("BORDER"))
    lay_group.pack(fill="x", pady=(0, 16))
    
    TkLabel(lay_group, text=_tr("theme_layout_label"), bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"), font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 10))

    # Читаем текущий пресет раскладки (поддержка старого ключа "layout"
    # реализована внутри theme_manager.load_theme() — merged содержит оба).
    _current_layout_name = current_theme.get("layout_preset") or current_theme.get("layout") or "classic"
    lay_var = tk.StringVar(value=_current_layout_name)
    for l_id, l_label in [("classic", _tr("theme_layout_classic")), ("compact", _tr("theme_layout_compact")), ("wide", _tr("theme_layout_wide"))]:
        tk.Radiobutton(lay_group, text=l_label, variable=lay_var, value=l_id, 
                       bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"), selectcolor=_c("BG_INPUT"), 
                       activebackground=_c("BG_CARD"), font=("Segoe UI", 12), anchor="w").pack(fill="x")

    # Честное предупреждение: большинство параметров (ширина левой панели,
    # отступы окна, отступы панелей, размер консоли/статусбара, отступы
    # textbox) теперь применяется СРАЗУ (см. apply_layout_preset() в
    # engine/gui/layout.py и apply_layout() во всех панелях). Единственное
    # исключение — переключение числа рядов тулбара (Compact ⇄ Classic/Wide,
    # toolbar_rows: 1 ⇄ 2) — оно требует перезапуска, см. apply_layout() в
    # engine/gui/toolbar.py (там это явное и осознанное ограничение).
    # ПРИМЕЧАНИЕ: намеренно НЕ используем t() для этого текста — ключ
    # "theme_layout_restart_note" не зарегистрирован в файлах локализации,
    # а t() в этом проекте может бросать исключение на отсутствующий ключ
    # (что и ломало открытие окна). Текст жёстко задан как constant.
    TkLabel(
        lay_group,
        text="Большинство параметров раскладки применяется сразу.\n"
             "Число рядов тулбара (Compact ⇄ Classic/Wide) вступит в силу\n"
             "только после перезапуска приложения.",
        bg=_c("BG_CARD"), fg=_c("TEXT_DIM"), font=("Segoe UI", 11),
        justify="left", anchor="w"
    ).pack(fill="x", pady=(8, 0))

    # ── Нижние кнопки ────────────────────────────────────────────────────────
    btn_row = TkFrame(main, bg=_c("BG_DARK"))
    # ИСПРАВЛЕНО: side="bottom" + упаковка ДО canvas/scrollbar (см. правку
    # выше) — гарантирует, что панель кнопок всегда закреплена внизу окна
    # на всю ширину, а прокручиваемый контент занимает оставшееся место
    # НАД ней, а не наоборот.
    btn_row.pack(side="bottom", fill="x", pady=(14, 0))

    # Разделительная линия над кнопками — чтобы визуально отделить их
    # от прокручиваемого контента (простая тонкая полоса через TkFrame).
    TkFrame(main, bg=_c("BORDER"), height=1).pack(side="bottom", fill="x", pady=(14, 0))

    # Теперь, когда нижняя панель кнопок уже закреплена (side="bottom"),
    # отдаём canvas/scrollbar всё оставшееся пространство.
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    def apply_and_save():
        selected_layout = lay_var.get()
        new_theme = {
            "colors": {k: v.get() for k, v in color_vars.items()},
            "fonts": {
                "main": font_main_var.get(),
                "size_main": font_size_var.get(),
                "mono": "Consolas", 
                "size_header": 14,
                "size_small": 9,
            },
            "geometry": {
                "padding_main": pad_var.get(),
                "padding_inner": 5,
                "item_spacing": 8,
            },
            # ВАЖНО: пишем именно "layout_preset" — это ключ, который читает
            # theme_manager.get_current_layout_preset_name(). save_theme()
            # сам синхронизирует старый ключ "layout" от этого значения
            # (см. engine/gui/theme_manager.py save_theme()), поэтому
            # обратная совместимость не ломается.
            "layout_preset": selected_layout,
        }
        save_theme(new_theme)

        # ── Live-применение раскладки ко всем панелям (если возможно) ──
        live_applied = False
        if callable(on_layout_changed):
            try:
                preset_dict = get_layout_preset(selected_layout)
                live_applied = bool(on_layout_changed(preset_dict))
            except Exception:
                live_applied = False

        if live_applied:
            messagebox.showinfo(
                "Тема",
                "Настройки темы сохранены и применены сразу.\n"
                "Число рядов тулбара (если менялось между Compact и\n"
                "Classic/Wide) вступит в силу после перезапуска приложения.",
                parent=win
            )
        else:
            messagebox.showinfo(
                "Тема",
                "Настройки темы сохранены! Перезапустите приложение для полного применения.",
                parent=win
            )
        win.destroy()

    _make_button(btn_row, _tr("theme_reset_btn"), lambda: win.destroy(), bg=_c("BG_INPUT"), font_size=11).pack(side="right", padx=(8, 0))
    _make_button(btn_row, _tr("theme_save_btn"), apply_and_save, bg=_c("BG_ACTIVE"), font_size=11).pack(side="right")

    scrollbar.config(command=canvas.yview)
