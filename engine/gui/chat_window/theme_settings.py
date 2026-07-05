from __future__ import annotations
import tkinter as tk
from tkinter import colorchooser, ttk, messagebox
import engine.gui.chat_window.state as state
from engine.gui.chat_window.custom_widgets import TkFrame, TkLabel, TkButton
from engine.gui.chat_window.ui_utils import _make_button, _set_dark_titlebar
from engine.gui.theme_manager import (
    load_theme, save_theme, get_layout_preset,
    get_custom_colors, set_custom_colors, reset_custom_colors,
    get_font_base_size, set_font_base_size as tm_set_font_base_size,
    get_saved_presets, save_named_preset, delete_named_preset, apply_named_preset,
)
from engine.gui.colors import (
    Colors, DARK_PALETTE, LIGHT_PALETTE, apply_palette,
    set_font_base_size as rt_set_font_base_size, scaled_font_size,
    BASE_FONT_SIZE_DEFAULT,
)
from engine.gui.theme import get_theme, set_theme
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


# ── Человекочитаемые русские названия РЕАЛЬНЫХ атрибутов Colors ──
# ИСПРАВЛЕНО (важно): раньше здесь редактировались 11 ключей из легаси-
# секции theme_settings.json["colors"] (BG_MAIN, ACCENT_DARK, SUCCESS...),
# которые физически НЕ СУЩЕСТВОВАЛИ как атрибуты engine.gui.colors.Colors —
# редактирование в конструкторе темы сохранялось в JSON, но никогда не
# применялось к реальному виду приложения (см. подробный комментарий в
# engine/gui/theme_manager.py DEFAULT_THEME). Теперь список ниже — это
# ВСЕ 29 настоящих ключей DARK_PALETTE/LIGHT_PALETTE из colors.py,
# сгруппированные по смыслу для удобства. Правки реально применяются через
# theme_manager.set_custom_colors() -> colors.apply_palette() (см. ниже).
COLOR_LABELS_RU = {
    "BG_DARK": "Фон окна",
    "BG_CARD": "Фон карточек",
    "BG_INPUT": "Фон полей ввода",
    "BG_HOVER": "Фон при наведении",
    "BG_ACTIVE": "Кнопка «Генерировать»",
    "BG_DANGER": "Кнопка «Отмена/Стоп»",
    "TEXT_MAIN": "Текст основной",
    "TEXT_DIM": "Текст приглушённый",
    "TEXT_SUCCESS": "Текст успеха",
    "TEXT_WARNING": "Текст предупреждения",
    "TEXT_ERROR": "Текст ошибки",
    "ACCENT": "Акцентный цвет",
    "BORDER": "Цвет границ",
    "PROGRESS_BG": "Прогресс-бар (фон)",
    "PROGRESS_FG": "Прогресс-бар (шкала)",
    "CHUNK_BG": "Подсветка чанка (фон)",
    "CHUNK_FG": "Подсветка чанка (текст)",
    "TOOLTIP_BG": "Фон подсказки",
    "MENU_BG": "Фон меню",
    "MENU_HOVER": "Меню — наведение",
    "MENU_ACTIVE": "Меню — активный пункт",
    "AI_ACCENT": "AI — акцент",
    "AI_ACCENT_HOVER": "AI — акцент (hover)",
    "AI_GROUP_BG": "AI — фон в тулбаре",
    "GROUP_BG": "Тулбар — фон группы",
    "GROUP_FILE_BG": "Группа «Файл»",
    "GROUP_OUTPUT_BG": "Группа «Вывод»",
    "GROUP_ACTION_BG": "Группа «Действие»",
    "GRADIENT_BOTTOM": "Градиент фона (низ)",
}

# Группировка ключей цвета для отображения в конструкторе темы — просто
# порядок и заголовки секций, на данные никак не влияет.
COLOR_GROUPS_RU = [
    ("Фоны", ["BG_DARK", "BG_CARD", "BG_INPUT", "BG_HOVER", "BG_ACTIVE", "BG_DANGER"]),
    ("Текст", ["TEXT_MAIN", "TEXT_DIM", "TEXT_SUCCESS", "TEXT_WARNING", "TEXT_ERROR"]),
    ("Акцент и границы", ["ACCENT", "BORDER"]),
    ("Прогресс-бар", ["PROGRESS_BG", "PROGRESS_FG"]),
    ("Подсветка текста при генерации", ["CHUNK_BG", "CHUNK_FG"]),
    ("Подсказки и меню", ["TOOLTIP_BG", "MENU_BG", "MENU_HOVER", "MENU_ACTIVE"]),
    ("AI-функции", ["AI_ACCENT", "AI_ACCENT_HOVER", "AI_GROUP_BG"]),
    ("Тулбар — группы кнопок", ["GROUP_BG", "GROUP_FILE_BG", "GROUP_OUTPUT_BG", "GROUP_ACTION_BG"]),
    ("Градиент фона", ["GRADIENT_BOTTOM"]),
]


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
    # ИСПРАВЛЕНО (по отзыву пользователя — окно было слишком большим):
    # было "720x800", уменьшено до более компактного размера. Плюс убран
    # лишний отступ слева у списка параметров (см. padx ниже и padx=15->10
    # у групп, а также сокращённая ширина подписи цвета: 32 -> 24 символа —
    # раньше значение было явно избыточным и создавало пустое пространство
    # между текстом подписи и кнопкой выбора цвета).
    win.geometry("620x680")
    win.minsize(480, 420)
    win.resizable(True, True)
    win.configure(bg=_c("BG_DARK"))
    win.transient(parent)
    win.grab_set()

    current_theme = load_theme()

    # Главный контейнер — отступ уменьшен (20 -> 12), чтобы не создавать
    # лишнего "воздуха" по краям всего окна.
    main = TkFrame(win, bg=_c("BG_DARK"))
    main.pack(fill="both", expand=True, padx=12, pady=12)

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
    # ИСПРАВЛЕНО (важно): TkFrame(..., padx=10, pady=12, ...) НЕ работал, если
    # customtkinter установлен — CTkFrame.__init__() в custom_widgets.py
    # принимает padx/pady как параметры, но нигде их не применяет (тихо
    # "проглатывает"), в отличие от bg/highlightbackground (те конвертируются
    # в fg_color/border_color). Из-за этого весь контент секций (подписи
    # цветов, поле ввода имени пресета и т.д.) прижимался почти вплотную к
    # краям рамки — читать было тяжело, поле пресета выглядело "невидимым".
    # Решение: разделяем каждую секцию на ВНЕШНИЙ контейнер (только рамка +
    # фон, без padx/pady) и ВНУТРЕННИЙ (реальный контент), у которого отступ
    # задаётся через .pack(padx=..., pady=...) — pack ВСЕГДА применяет эти
    # параметры, независимо от того, CTkFrame это или обычный tk.Frame.
    # Переменная "colors_group" (и так же ниже для остальных секций)
    # намеренно указывает на ВНУТРЕННИЙ контейнер — все дочерние виджеты
    # ниже по коду не пришлось менять.
    colors_group_outer = TkFrame(scroll_frame, bg=_c("BG_CARD"),
                                 highlightthickness=1, highlightbackground=_c("BORDER"))
    colors_group_outer.pack(fill="x", pady=(0, 12))
    colors_group = TkFrame(colors_group_outer, bg=_c("BG_CARD"))
    colors_group.pack(fill="both", expand=True, padx=14, pady=12)

    # ИСПРАВЛЕНО: раньше здесь редактировались 11 "мёртвых" ключей (см.
    # комментарий у COLOR_LABELS_RU выше) — теперь редактируются РЕАЛЬНЫЕ
    # 29 атрибутов Colors для ТЕКУЩЕЙ активной темы (dark/light). Тема
    # берётся через engine.gui.theme.get_theme() — тот же переключатель
    # ☀/🌙, что и в textbox.py. Каждая тема (dark/light) хранит свои
    # переопределения отдельно (theme_manager.get/set_custom_colors),
    # поэтому настройка цветов в тёмной теме не портит светлую и наоборот.
    _active_theme_name = get_theme()
    _base_palette = DARK_PALETTE if _active_theme_name == "dark" else LIGHT_PALETTE
    _existing_custom = get_custom_colors(_active_theme_name)

    _theme_display_name = "тёмная" if _active_theme_name == "dark" else "светлая"
    TkLabel(colors_group, text=f"Цвета интерфейса — тема «{_theme_display_name}»",
            bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"),
            font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 4))
    TkLabel(colors_group,
            text="Переключите тему (☀/🌙 в главном окне) перед открытием этого\n"
                 "окна, чтобы настроить цвета другой темы — они хранятся раздельно.",
            bg=_c("BG_CARD"), fg=_c("TEXT_DIM"), font=("Segoe UI", 9),
            justify="left", anchor="w").pack(anchor="w", pady=(0, 10))

    color_vars = {}
    color_buttons = {}  # {color_name: button} — нужно для _reset_colors_to_default(),
                        # чтобы сброс перекрашивал сами кнопки, а не только их StringVar

    def pick_color(name, var, btn):
        color = colorchooser.askcolor(initialcolor=var.get())[1]
        if color:
            var.set(color)
            btn.config(bg=color)

    for group_title, color_names in COLOR_GROUPS_RU:
        TkLabel(colors_group, text=group_title, bg=_c("BG_CARD"), fg=_c("ACCENT"),
                font=("Segoe UI", 11, "bold"), anchor="w").pack(fill="x", pady=(8, 4))
        for color_name in color_names:
            # Значение по умолчанию — из встроенной палитры, если
            # пользователь его не переопределял (_existing_custom).
            current_val = _existing_custom.get(color_name, _base_palette.get(color_name, "#ffffff"))
            row = TkFrame(colors_group, bg=_c("BG_CARD"))
            row.pack(fill="x", pady=2)

            var = tk.StringVar(value=current_val)
            color_vars[color_name] = var

            TkLabel(row, text=_color_label(color_name), bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"),
                    font=("Segoe UI", 11), width=24, anchor="w").pack(side="left")

            # Кнопка выбора цвета — сама показывает текущий выбранный цвет
            btn = TkButton(row, text=" 🎨 ",
                           bg=current_val, fg="white",
                           width=5, relief="flat", cursor="hand2")
            # ИСПРАВЛЕН ПРЕДСУЩЕСТВОВАВШИЙ БАГ (был в коде ещё до этой
            # правки, просто не был заметен раньше): раньше здесь было
            # `b=btn: pick_color(n, v, btn)` — внутри тела лямбды
            # использовалась свободная переменная "btn" из внешней области
            # видимости (late binding), а не параметр "b" (early binding).
            # Так как переменная "btn" в цикле переопределяется на каждой
            # итерации, к моменту реального клика она уже указывала на
            # ПОСЛЕДНЮЮ созданную кнопку в цикле — клик по любой кнопке,
            # кроме самой последней, перекрашивал не тот цвет. Теперь
            # тело лямбды использует "b" (параметр по умолчанию),
            # который корректно захватывает кнопку именно этой итерации.
            btn.config(command=lambda n=color_name, v=var, b=btn: pick_color(n, v, b))
            btn.pack(side="left", padx=10)
            color_buttons[color_name] = btn

    def _reset_colors_to_default():
        """Сбрасывает ВСЕ цвета текущей темы обратно к встроенной палитре
        (в самих полях формы — реальный сброс в JSON происходит только
        по кнопке 'Сохранить', как и остальные секции этого окна).

        ИСПРАВЛЕНО: раньше здесь обновлялся только var.set(...) — сама
        кнопка-превью цвета (color_buttons[name]) визуально оставалась
        в старом цвете до следующего ручного клика по ней. Теперь
        обновляется и StringVar, и bg самой кнопки."""
        for color_name, var in color_vars.items():
            default_val = _base_palette.get(color_name, "#ffffff")
            var.set(default_val)
            btn_ref = color_buttons.get(color_name)
            if btn_ref is not None:
                try:
                    btn_ref.config(bg=default_val)
                except Exception:
                    pass

    TkButton(colors_group, text="↺ Сбросить цвета этой темы к стандартным",
             command=_reset_colors_to_default,
             bg=_c("BG_INPUT"), fg=_c("TEXT_MAIN"), relief="flat",
             font=("Segoe UI", 10), cursor="hand2", padx=10, pady=6
             ).pack(anchor="w", pady=(10, 0))

    # ── Секция Типографики ──────────────────────────────────────────────
    # ИСПРАВЛЕНО: раньше здесь было поле "имя шрифта" (font_main_var) —
    # тоже "мёртвое": семейство шрифта нигде в проекте не читалось из
    # theme_settings.json, все виджеты хардкодят "Segoe UI"/"Consolas"
    # напрямую в коде. Убрано, чтобы не создавать иллюзию несуществующей
    # функциональности. Вместо него — РЕАЛЬНЫЙ рабочий слайдер базового
    # размера шрифта (colors.scaled_font_size() масштабирует им ВСЕ
    # хардкоженные font=(..., N) по всему проекту, КРОМЕ текстового поля
    # ввода/редактора — там свой отдельный независимый механизм, слайдер
    # "Aa" в textbox.py, который НЕ трогаем).
    # См. пояснение про padx/pady у TkFrame выше (секция "Цветов") — тот же
    # паттерн внешний/внутренний контейнер применяется здесь.
    fonts_group_outer = TkFrame(scroll_frame, bg=_c("BG_CARD"),
                                highlightthickness=1, highlightbackground=_c("BORDER"))
    fonts_group_outer.pack(fill="x", pady=(0, 12))
    fonts_group = TkFrame(fonts_group_outer, bg=_c("BG_CARD"))
    fonts_group.pack(fill="both", expand=True, padx=14, pady=12)

    TkLabel(fonts_group, text="Размер шрифта интерфейса", bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"),
            font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 4))
    TkLabel(fonts_group,
            text="Меняет размер текста во всём приложении (кнопки, подписи,\n"
                 "консоль, окна). НЕ влияет на текстовое поле ввода — там\n"
                 "отдельный размер шрифта (кнопка «Aa» рядом с полем ввода).",
            bg=_c("BG_CARD"), fg=_c("TEXT_DIM"), font=("Segoe UI", 9),
            justify="left", anchor="w").pack(anchor="w", pady=(0, 10))

    font_base_size_var = tk.IntVar(value=get_font_base_size())

    row_fs = TkFrame(fonts_group, bg=_c("BG_CARD"))
    row_fs.pack(fill="x")

    font_size_value_label = TkLabel(row_fs, text=str(font_base_size_var.get()),
                                    bg=_c("BG_CARD"), fg=_c("ACCENT"),
                                    font=("Segoe UI", 12, "bold"), width=3, anchor="e")
    font_size_value_label.pack(side="right", padx=(6, 0))

    def _on_font_size_slider(value):
        try:
            size = int(round(float(value)))
        except Exception:
            return
        font_size_value_label.config(text=str(size))

    # ПРИМЕЧАНИЕ: используем и command=, и trace_add на самой переменной —
    # tk.Scale.command вызывается только при ручном взаимодействии
    # пользователя с ползунком мышью/клавиатурой, но НЕ при программном
    # var.set(...) (например, из кнопки "Сбросить ВСЁ" ниже). trace_add
    # гарантированно ловит оба случая, поэтому числовая подпись справа от
    # слайдера всегда синхронна со значением переменной.
    font_base_size_var.trace_add(
        "write", lambda *_: font_size_value_label.config(text=str(font_base_size_var.get()))
    )

    font_size_scale = tk.Scale(
        row_fs, from_=6, to=24, orient="horizontal", variable=font_base_size_var,
        command=_on_font_size_slider,
        bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"), highlightthickness=0,
        troughcolor=_c("BG_INPUT")
    )
    font_size_scale.pack(side="left", fill="x", expand=True)

    # ПРИМЕЧАНИЕ (удалено): здесь раньше была секция "Геометрия и Отступы"
    # со слайдером padding_main — она была так же "мертва", как раньше были
    # цвета: geometry.padding_main нигде в проекте не читался, кроме этого
    # самого файла. Настоящее управление отступами уже реализовано и
    # РЕАЛЬНО РАБОТАЕТ через пресеты раскладки ниже (Classic/Compact/Wide —
    # padding_main_x/y, panel_spacing и т.д., см. engine/gui/layout.py).
    # Секция убрана, чтобы не дублировать функциональность и не создавать
    # у пользователя ложное впечатление о ещё одном независимом регуляторе
    # отступов (заодно немного уменьшает высоту всего окна).

    # ── Секция Расположения ────────────────────────────────────────────────────────
    # См. пояснение про padx/pady у TkFrame выше (секция "Цветов").
    lay_group_outer = TkFrame(scroll_frame, bg=_c("BG_CARD"),
                              highlightthickness=1, highlightbackground=_c("BORDER"))
    lay_group_outer.pack(fill="x", pady=(0, 12))
    lay_group = TkFrame(lay_group_outer, bg=_c("BG_CARD"))
    lay_group.pack(fill="both", expand=True, padx=14, pady=12)

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

    # ── Секция Пресетов (НОВОЕ) ──────────────────────────────────────────
    # Пресет — это именованный "снимок" ВСЕХ трёх настроек этого окна разом
    # (цвета текущей темы + базовый размер шрифта + раскладка). Хранится в
    # theme_settings.json -> "saved_presets" (см. theme_manager.py). Список
    # пресетов не ограничен — пользователь может создать сколько угодно.
    # См. пояснение про padx/pady у TkFrame выше (секция "Цветов") — именно
    # из-за этого бага поле ввода имени пресета выглядело "почти невидимым"
    # (было прижато вплотную к краю рамки без реального отступа).
    presets_group_outer = TkFrame(scroll_frame, bg=_c("BG_CARD"),
                                  highlightthickness=1, highlightbackground=_c("BORDER"))
    presets_group_outer.pack(fill="x", pady=(0, 12))
    presets_group = TkFrame(presets_group_outer, bg=_c("BG_CARD"))
    presets_group.pack(fill="both", expand=True, padx=14, pady=12)

    TkLabel(presets_group, text="Пресеты темы", bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"),
            font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 4))
    TkLabel(presets_group,
            text="Пресет сохраняет цвета текущей темы, размер шрифта и\n"
                 "раскладку одним именем — чтобы быстро переключаться между\n"
                 "готовыми настройками.",
            bg=_c("BG_CARD"), fg=_c("TEXT_DIM"), font=("Segoe UI", 9),
            justify="left", anchor="w").pack(anchor="w", pady=(0, 10))

    # -- Список существующих пресетов --
    preset_list_row = TkFrame(presets_group, bg=_c("BG_CARD"))
    preset_list_row.pack(fill="x", pady=(0, 8))

    preset_names_var = tk.StringVar()

    def _refresh_preset_list():
        names = sorted(get_saved_presets().keys())
        preset_combo["values"] = names
        if names:
            if preset_names_var.get() not in names:
                preset_names_var.set(names[0])
        else:
            preset_names_var.set("")

    preset_combo = ttk.Combobox(preset_list_row, textvariable=preset_names_var,
                                state="readonly", font=("Segoe UI", 10))
    preset_combo.pack(side="left", fill="x", expand=True, padx=(0, 8))

    def _apply_selected_preset():
        name = preset_names_var.get()
        if not name:
            messagebox.showwarning("Пресеты", "Сначала выберите пресет из списка.", parent=win)
            return
        snapshot = apply_named_preset(name)
        if snapshot is None:
            messagebox.showerror("Пресеты", f"Пресет «{name}» не найден.", parent=win)
            _refresh_preset_list()
            return
        # Живое применение цветов/шрифта прямо в открытом окне конструктора —
        # честно предупреждаем, что полный эффект по всему приложению
        # виден при следующем открытии/перезапуске (как и у обычного
        # сохранения — см. apply_and_save() ниже).
        preset_theme_name = snapshot.get("theme_name", _active_theme_name)
        if preset_theme_name != _active_theme_name:
            messagebox.showinfo(
                "Пресеты",
                f"Пресет «{name}» был сохранён для {'тёмной' if preset_theme_name == 'dark' else 'светлой'} темы.\n"
                "Он применён, но чтобы увидеть цвета — переключите тему (☀/🌙)\n"
                "и откройте конструктор темы заново.",
                parent=win
            )
        else:
            try:
                apply_palette(preset_theme_name)
            except Exception:
                pass
        try:
            rt_set_font_base_size(snapshot.get("font_base_size", 10))
        except Exception:
            pass
        messagebox.showinfo("Пресеты", f"Пресет «{name}» применён. Откройте конструктор\nтемы заново, чтобы увидеть все изменения в полях.", parent=win)
        win.destroy()

    def _delete_selected_preset():
        name = preset_names_var.get()
        if not name:
            return
        if messagebox.askyesno("Пресеты", f"Удалить пресет «{name}»?", parent=win):
            delete_named_preset(name)
            _refresh_preset_list()

    TkButton(preset_list_row, text="Применить", command=_apply_selected_preset,
             bg=_c("BG_ACTIVE"), fg=_c("TEXT_MAIN"), relief="flat",
             font=("Segoe UI", 10), cursor="hand2", padx=8, pady=4
             ).pack(side="left", padx=(0, 4))
    TkButton(preset_list_row, text="Удалить", command=_delete_selected_preset,
             bg=_c("BG_DANGER"), fg=_c("TEXT_MAIN"), relief="flat",
             font=("Segoe UI", 10), cursor="hand2", padx=8, pady=4
             ).pack(side="left")

    # -- Сохранение текущих настроек как нового пресета --
    TkLabel(presets_group, text="Имя нового пресета:", bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"),
            font=("Segoe UI", 10), anchor="w").pack(fill="x", pady=(8, 4))

    save_preset_row = TkFrame(presets_group, bg=_c("BG_CARD"))
    save_preset_row.pack(fill="x")

    new_preset_name_var = tk.StringVar()
    # ИСПРАВЛЕНО: добавлена видимая рамка (highlightthickness=1,
    # highlightbackground=BORDER) — раньше поле было тем же bg, что и фон
    # секции, плюс padx/pady у родительского TkFrame не применялись
    # (см. комментарий у presets_group_outer выше), из-за чего поле
    # визуально сливалось с фоном и выглядело "почти невидимым".
    preset_name_entry = tk.Entry(save_preset_row, textvariable=new_preset_name_var,
                                 bg=_c("BG_INPUT"), fg=_c("TEXT_MAIN"),
                                 insertbackground=_c("TEXT_MAIN"), relief="flat",
                                 highlightthickness=1, highlightbackground=_c("BORDER"),
                                 highlightcolor=_c("ACCENT"),
                                 font=("Segoe UI", 10))
    preset_name_entry.pack(side="left", fill="x", expand=True, padx=(0, 8), ipady=6)

    def _save_current_as_preset():
        name = new_preset_name_var.get().strip()
        if not name:
            messagebox.showwarning("Пресеты", "Введите имя пресета.", parent=win)
            return
        existing = get_saved_presets()
        if name in existing:
            if not messagebox.askyesno("Пресеты", f"Пресет «{name}» уже существует.\nПерезаписать его?", parent=win):
                return
        # Снимок ТЕКУЩЕГО состояния полей формы (ещё не сохранённого через
        # apply_and_save) — так пользователь может подготовить пресет и
        # сохранить его, не закрывая окно кнопкой "Сохранить".
        current_custom_colors = {}
        for color_name, var in color_vars.items():
            val = var.get()
            if val != _base_palette.get(color_name):
                current_custom_colors[color_name] = val
        snapshot = {
            "custom_colors": current_custom_colors,
            "theme_name": _active_theme_name,
            "font_base_size": font_base_size_var.get(),
            "layout_preset": lay_var.get(),
        }
        save_named_preset(name, snapshot)
        new_preset_name_var.set("")
        _refresh_preset_list()
        preset_names_var.set(name)
        messagebox.showinfo("Пресеты", f"Пресет «{name}» сохранён.", parent=win)

    TkButton(save_preset_row, text="Сохранить как пресет", command=_save_current_as_preset,
             bg=_c("BG_INPUT"), fg=_c("TEXT_MAIN"), relief="flat",
             font=("Segoe UI", 10), cursor="hand2", padx=8, pady=4
             ).pack(side="left")

    _refresh_preset_list()

    # -- Полный сброс всех настроек темы (цвета + шрифт + раскладка) --
    def _reset_everything_to_factory():
        if not messagebox.askyesno(
            "Сброс настроек",
            "Сбросить ВСЕ настройки темы (цвета, размер шрифта, раскладку)\n"
            "к заводским значениям? Сохранённые именованные пресеты не\n"
            "будут удалены.",
            parent=win
        ):
            return
        _reset_colors_to_default()
        font_base_size_var.set(BASE_FONT_SIZE_DEFAULT)
        font_size_value_label.config(text=str(BASE_FONT_SIZE_DEFAULT))
        lay_var.set("classic")
        messagebox.showinfo(
            "Сброс настроек",
            "Поля сброшены к заводским значениям.\nНажмите «Сохранить», чтобы применить.",
            parent=win
        )

    TkButton(presets_group, text="↺ Сбросить ВСЁ (цвета + шрифт + раскладка) к заводским",
             command=_reset_everything_to_factory,
             bg=_c("BG_DANGER"), fg=_c("TEXT_MAIN"), relief="flat",
             font=("Segoe UI", 10), cursor="hand2", padx=10, pady=6
             ).pack(anchor="w", pady=(10, 0))

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

        # ИСПРАВЛЕНО: цвета теперь сохраняются через set_custom_colors()
        # (реально применяемая система — colors.apply_palette()), а НЕ
        # через легаси-ключ "colors" в new_theme (тот больше никто не
        # читает, см. комментарий в theme_manager.py DEFAULT_THEME).
        # Сохраняем только то, что отличается от встроенной палитры —
        # если пользователь оставил значение как есть, лишний ключ в JSON
        # не создаём (чище дифф в файле настроек, меньше "мусора").
        new_custom_colors = {}
        for color_name, var in color_vars.items():
            val = var.get()
            if val != _base_palette.get(color_name):
                new_custom_colors[color_name] = val
        set_custom_colors(_active_theme_name, new_custom_colors)
        # Применяем сразу — это безопасно и мгновенно видно в уже открытых
        # окнах, которые перечитывают Colors.* при следующей перерисовке
        # (кнопки/лейблы, создаваемые заново), полноценный эффект во ВСЕХ
        # существующих окнах — после их следующего открытия/перезапуска
        # приложения (см. пояснение в docstring apply_palette()).
        try:
            apply_palette(_active_theme_name)
        except Exception:
            pass

        # ИСПРАВЛЕНО: базовый размер шрифта теперь сохраняется через
        # РЕАЛЬНО работающий theme_manager.set_font_base_size() (легаси-
        # ключи "fonts"/"geometry" убраны — они физически ни на что не
        # влияли, см. комментарии выше). Применяем сразу в runtime
        # (colors.set_font_base_size) — часть окон подхватят новый размер
        # только при следующем открытии (см. пояснение в docstring
        # colors.scaled_font_size()), но само значение уже действует.
        new_font_base_size = font_base_size_var.get()
        tm_set_font_base_size(new_font_base_size)
        try:
            rt_set_font_base_size(new_font_base_size)
        except Exception:
            pass

        new_theme = {
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
                "Настройки сохранены. Цвета и размер шрифта применены сразу\n"
                "к этому окну и новым виджетам (остальные открытые окна и\n"
                "число рядов тулбара обновятся после их следующего открытия\n"
                "или перезапуска приложения).",
                parent=win
            )
        else:
            messagebox.showinfo(
                "Тема",
                "Настройки сохранены! Цвета и размер шрифта применятся ко\n"
                "всем окнам при следующем открытии, полностью — после\n"
                "перезапуска приложения.",
                parent=win
            )
        win.destroy()

    _make_button(btn_row, _tr("theme_reset_btn"), lambda: win.destroy(), bg=_c("BG_INPUT"), font_size=11).pack(side="right", padx=(8, 0))
    _make_button(btn_row, _tr("theme_save_btn"), apply_and_save, bg=_c("BG_ACTIVE"), font_size=11).pack(side="right")

    scrollbar.config(command=canvas.yview)
