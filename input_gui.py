"""Desktop UI for imported controller/keyboard bindings and reversible icon styles."""
from pathlib import Path
import queue
import threading

import input_icons
from keyboard_art import label as keycap_label
from keyboard_bindings import (
    DEFAULTS, KEY_NAMES, PAD_DEFAULTS, PAD_SOURCES, SOURCE_TO_CONTROL,
    defaults, from_controls, from_pad_controls, load, save,
)

NAMES = {
    'Cross': 'Cross / Xbox A',
    'Circle': 'Circle / Xbox B',
    'Square': 'Square / Xbox X',
    'Triangle': 'Triangle / Xbox Y',
    'L1': 'L1 / LB (Left bumper)',
    'R1': 'R1 / RB (Right bumper)',
    'L2': 'L2 / LT (Left trigger)',
    'R2': 'R2 / RT (Right trigger)',
    'L3': 'L3 (Left stick click)',
    'R3': 'R3 (Right stick click)',
    'Options': 'Options / Pause',
    'TouchPad': 'Touchpad / Select',
    'TouchPadRight': 'Touchpad right side',
    'Up': 'D-Pad Up',
    'Down': 'D-Pad Down',
    'Left': 'D-Pad Left',
    'Right': 'D-Pad Right',
    'LeftStickUp': 'Left stick up',
    'LeftStickDown': 'Left stick down',
    'LeftStickLeft': 'Left stick left',
    'LeftStickRight': 'Left stick right',
    'RightStickUp': 'Right stick up',
    'RightStickDown': 'Right stick down',
    'RightStickLeft': 'Right stick left',
    'RightStickRight': 'Right stick right',
}

PAD_SOURCE_LABELS = {
    'South': ('A', 'Cross', 'South — Xbox A / PS Cross'),
    'East': ('B', 'Circle', 'East — Xbox B / PS Circle'),
    'West': ('X', 'Square', 'West — Xbox X / PS Square'),
    'North': ('Y', 'Triangle', 'North — Xbox Y / PS Triangle'),
    'LeftShoulder': ('LB', 'L1', 'LeftShoulder — LB / L1'),
    'RightShoulder': ('RB', 'R1', 'RightShoulder — RB / R1'),
    'LeftTrigger': ('LT', 'L2', 'LeftTrigger — LT / L2'),
    'RightTrigger': ('RT', 'R2', 'RightTrigger — RT / R2'),
    'LeftStick': ('L3', 'L3', 'LeftStick — L3 Click'),
    'RightStick': ('R3', 'R3', 'RightStick — R3 Click'),
    'Start': ('Menu', 'Options', 'Start — Menu / Options'),
    'Touchpad': ('View', 'TouchPad', 'Touchpad — View / Touchpad'),
    'Back': ('View', 'Share', 'Back — View / Share'),
    'Guide': ('Guide', 'PS', 'Guide — Home / Guide'),
    'Misc1': ('Share', 'Mic', 'Misc1 — Share / Capture'),
    'DpadUp': ('Up', 'Up', 'DpadUp — D-Pad Up'),
    'DpadDown': ('Down', 'Down', 'DpadDown — D-Pad Down'),
    'DpadLeft': ('Left', 'Left', 'DpadLeft — D-Pad Left'),
    'DpadRight': ('Right', 'Right', 'DpadRight — D-Pad Right'),
    'LeftPaddle1': ('P1', 'P1', 'LeftPaddle1'),
    'RightPaddle1': ('P2', 'P2', 'RightPaddle1'),
    'LeftPaddle2': ('P3', 'P3', 'LeftPaddle2'),
    'RightPaddle2': ('P4', 'P4', 'RightPaddle2'),
}

COMMON_KEYS = (
    'J', 'K', 'L', 'I', 'Q', 'E', 'Z', 'C', 'W', 'A', 'S', 'D', 'T', 'F', 'G', 'H',
    'Space', 'Return', 'Tab', 'Backspace', 'Left Shift', 'Left Ctrl', 'Left Alt',
    'Up', 'Down', 'Left', 'Right',
    'Mouse:Left', 'Mouse:Right', 'Mouse:Middle', 'Mouse:X1', 'Mouse:X2',
)

BG_DARK = '#18191e'
CARD_BG = '#21232a'
CARD_BORDER = '#373b46'
SURFACE_BG = '#1b1d24'
SURFACE_HOVER = '#2b2e37'
ACCENT = '#f13141'
ACCENT_HOVER = '#ff4757'
TEXT_WHITE = '#ffffff'
TEXT_MUTED = '#9ca0ad'

XBOX_BTN_COLORS = {
    'Cross': ('A', (113, 207, 133, 255)),
    'Circle': ('B', (244, 117, 125, 255)),
    'Square': ('X', (117, 177, 247, 255)),
    'Triangle': ('Y', (244, 205, 100, 255)),
}
PS_BTN_COLORS = {
    'Triangle': ('triangle', (99, 211, 177, 255)),
    'Circle': ('circle', (242, 129, 154, 255)),
    'Cross': ('cross', (124, 177, 247, 255)),
    'Square': ('square', (209, 151, 222, 255)),
}


def _load_ui_font(size, bold=False):
    from PIL import ImageFont
    candidates = ['segoeuib.ttf' if bold else 'segoeui.ttf', 'arialbd.ttf' if bold else 'arial.ttf']
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _draw_controller_glyph(draw, style, target_ctrl, x, y, w, h, scale, enabled=True):
    muted = (156, 160, 173, 255)
    if style == 'xbox' and target_ctrl in XBOX_BTN_COLORS:
        letter, col = XBOX_BTN_COLORS[target_ctrl]
        col = col if enabled else muted
        size = min(w, h)
        cx = x + (w - size) / 2
        cy = y + (h - size) / 2
        draw.ellipse((cx, cy, cx + size, cy + size), outline=col, width=max(2, round(1.8 * scale)))
        fnt = _load_ui_font(round(size * 0.6), bold=True)
        bbox = draw.textbbox((0, 0), letter, font=fnt)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text((cx + (size - tw) / 2 - bbox[0], cy + (size - th) / 2 - bbox[1]), letter, font=fnt, fill=col)
    elif style == 'playstation' and target_ctrl in PS_BTN_COLORS:
        shape, col = PS_BTN_COLORS[target_ctrl]
        col = col if enabled else muted
        size = min(w, h)
        cx = x + (w - size) / 2
        cy = y + (h - size) / 2
        pen_w = max(2, round(1.8 * scale))
        if shape == 'circle':
            draw.ellipse((cx, cy, cx + size, cy + size), outline=col, width=pen_w)
        else:
            inset = round(size * 0.1)
            x0, y0, x1, y1 = cx + inset, cy + inset, cx + size - inset, cy + size - inset
            if shape == 'triangle':
                draw.polygon([((x0 + x1) / 2, y0), (x1, y1), (x0, y1)], outline=col, width=pen_w)
            elif shape == 'cross':
                draw.line((x0, y0, x1, y1), fill=col, width=pen_w)
                draw.line((x1, y0, x0, y1), fill=col, width=pen_w)
            else:
                draw.rectangle((x0, y0, x1, y1), outline=col, width=pen_w)
    else:
        xb_lbl = {'L1': 'LB', 'R1': 'RB', 'L2': 'LT', 'R2': 'RT', 'L3': 'L3', 'R3': 'R3', 'Options': 'MENU', 'TouchPad': 'VIEW'}
        ps_lbl = {'L1': 'L1', 'R1': 'R1', 'L2': 'L2', 'R2': 'R2', 'L3': 'L3', 'R3': 'R3', 'Options': 'OPT', 'TouchPad': 'PAD'}
        txt = (xb_lbl if style == 'xbox' else ps_lbl).get(target_ctrl, (target_ctrl or '-')[:4].upper())
        col = (235, 237, 242, 255) if enabled else muted
        draw.rounded_rectangle((x, y + 2 * scale, x + w, y + h - 2 * scale), radius=5 * scale, fill=(45, 49, 60, 255), outline=col, width=max(1, round(1.4 * scale)))
        fnt = _load_ui_font(round(h * 0.44), bold=True)
        bbox = draw.textbbox((0, 0), txt, font=fnt)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text((x + (w - tw) / 2 - bbox[0], y + (h - th) / 2 - bbox[1]), txt, font=fnt, fill=col)


def _render_selector_card(app_dir, mode, selected, hovered, enabled, binding, width=210, height=74):
    from PIL import Image, ImageDraw
    from keyboard_art import render

    scale = 2
    w, h = width * scale, height * scale
    im = Image.new('RGBA', (w, h), (33, 35, 42, 255))
    draw = ImageDraw.Draw(im)

    if selected and enabled:
        surface, border, border_w = (54, 33, 42, 255), (241, 49, 65, 255), 3
    elif hovered and enabled:
        surface, border, border_w = (43, 46, 55, 255), (90, 95, 112, 255), 2
    else:
        surface, border, border_w = (27, 29, 36, 255), (65, 69, 81, 255), 2

    draw.rounded_rectangle((2, 2, w - 3, h - 3), radius=8 * scale, fill=surface, outline=border, width=border_w)

    accent_col = (241, 49, 65, 255)
    muted_col = (156, 160, 173, 255)
    white_col = (255, 255, 255, 255) if enabled else muted_col

    rx, ry, rsize = 14 * scale, 12 * scale, 11 * scale
    ring_col = accent_col if (selected and enabled) else muted_col
    draw.ellipse((rx, ry, rx + rsize, ry + rsize), outline=ring_col, width=max(2, round(1.5 * scale)))
    if selected:
        dot_pad = 3 * scale
        draw.ellipse((rx + dot_pad, ry + dot_pad, rx + rsize - dot_pad, ry + rsize - dot_pad), fill=ring_col)

    title_map = {'xbox': 'Xbox', 'keyboard': 'Keyboard', 'playstation': 'PlayStation'}
    badge_map = {'xbox': 'MOD', 'keyboard': 'MOD', 'playstation': 'CUSTOM' if binding.has_custom_pad() else 'DEFAULT'}
    sub_map = {
        'xbox': 'Custom pad' if binding.has_custom_pad() else 'Applies mod',
        'keyboard': 'Custom keys',
        'playstation': 'Custom pad' if binding.has_custom_pad() else 'Original icons',
    }

    title_font = _load_ui_font(13 * scale, bold=True)
    badge_font = _load_ui_font(8 * scale, bold=True)
    sub_font = _load_ui_font(10 * scale, bold=False)

    draw.text((31 * scale, 8 * scale), title_map[mode], font=title_font, fill=white_col)
    badge_txt = badge_map[mode]
    bw = draw.textlength(badge_txt, font=badge_font)
    draw.text((w - 12 * scale - bw, 12 * scale), badge_txt, font=badge_font, fill=muted_col)

    icon_y = 38 * scale
    pad_map = binding.pad_controls()
    if mode in ('xbox', 'playstation'):
        order = ('Cross', 'Circle', 'Square', 'Triangle') if mode == 'xbox' else ('Triangle', 'Circle', 'Cross', 'Square')
        for i, ctrl in enumerate(order):
            src_btn = pad_map.get(ctrl)
            target_ctrl = SOURCE_TO_CONTROL.get(src_btn, ctrl) if src_btn else ctrl
            cx = (15 + i * 28) * scale
            _draw_controller_glyph(draw, mode, target_ctrl, cx, icon_y, 20 * scale, 20 * scale, scale, enabled)
    else:
        cap_size = 22 * scale
        for i, ctrl in enumerate(('Cross', 'Circle', 'Square', 'Triangle')):
            cx = (14 + i * 27) * scale
            cy = icon_y - 1 * scale
            pixels = render(cap_size, cap_size, dict(controls=[ctrl], layout='row'), binding)
            cap = Image.frombytes('RGBA', (cap_size, cap_size), pixels)
            im.alpha_composite(cap, (cx, cy))

    sub_txt = sub_map[mode]
    sw = draw.textlength(sub_txt, font=sub_font)
    draw.text((w - 12 * scale - sw, 42 * scale), sub_txt, font=sub_font, fill=muted_col)

    return im.resize((width, height), Image.Resampling.LANCZOS)


def _render_preview(app_dir, binding, style='keyboard', width=648):
    from PIL import Image, ImageDraw, ImageFont
    from keyboard_art import render

    scale = 2 if style in ('xbox', 'playstation') else 1
    w, h = width * scale, 42 * scale
    im = Image.new('RGBA', (w, h), (27, 29, 36, 255))
    draw = ImageDraw.Draw(im)
    draw.rounded_rectangle((0, 0, w - 1, h - 1), radius=6 * scale, fill=(27, 29, 36, 255), outline=(55, 59, 70, 255), width=scale)

    x = 14 * scale
    font = ImageFont.truetype(str(app_dir / 'keyboard-art/font/BarlowCondensed-Bold.ttf'), 20 * scale)
    prompts = [
        ('Cross', 'SELECT', 26 if style != 'keyboard' else 32),
        ('Circle', 'BACK', 26 if style != 'keyboard' else 32),
        ('Triangle', 'SIMULATE', 26 if style != 'keyboard' else 32),
        ('L1', 'PREV TAB', 34 if style != 'keyboard' else 36),
        ('R1', 'NEXT TAB', 34 if style != 'keyboard' else 36),
    ]
    pad_map = binding.pad_controls()
    for control, text, icon_w in prompts:
        if style == 'keyboard':
            pixels = render(icon_w, 32, dict(controls=[control], layout='row'), binding)
            icon = Image.frombytes('RGBA', (icon_w, 32), pixels)
            im.paste(icon, (round(x), 5), icon)
        else:
            src_btn = pad_map.get(control)
            target_ctrl = SOURCE_TO_CONTROL.get(src_btn, control) if src_btn else control
            _draw_controller_glyph(draw, style, target_ctrl, x, 8 * scale, icon_w * scale, 26 * scale, scale, True)
        x += (icon_w + 8) * scale
        draw.text((x, 11 * scale), text, font=font, fill=(244, 244, 245, 255))
        x += draw.textlength(text, font=font) + 26 * scale

    if scale > 1:
        im = im.resize((width, 42), Image.Resampling.LANCZOS)
    return im.convert('RGB')


def _summary_text(binding, style):
    if style == 'keyboard':
        pairs = [
            ('A/Cross', binding.controls.get('Cross')),
            ('B/Circle', binding.controls.get('Circle')),
            ('X/Square', binding.controls.get('Square')),
            ('Y/Triangle', binding.controls.get('Triangle')),
            ('L1/R1', f"{binding.controls.get('L1') or '-'} / {binding.controls.get('R1') or '-'}"),
            ('Start', binding.controls.get('Options')),
        ]
        return '   •   '.join(f'{name}: {val or "Unbound"}' for name, val in pairs)
    pad = binding.pad_controls()
    idx = 0 if style == 'xbox' else 1
    def lbl(ctrl):
        src = pad.get(ctrl)
        return PAD_SOURCE_LABELS.get(src, ('Unbound', 'Unbound', 'Unbound'))[idx] if src else 'Unbound'
    pairs = [
        ('Cross/A', lbl('Cross')),
        ('Circle/B', lbl('Circle')),
        ('Square/X', lbl('Square')),
        ('Triangle/Y', lbl('Triangle')),
        ('L1/R1', f"{lbl('L1')} / {lbl('R1')}"),
        ('L2/R2', f"{lbl('L2')} / {lbl('R2')}"),
    ]
    return '   •   '.join(f'{name} → {val}' for name, val in pairs)


def gui(app_dir, version, license_text):
    import tkinter as tk
    from tkinter import filedialog, messagebox, simpledialog, ttk

    window = tk.Tk()
    window.title('EA SPORTS UFC 6 — Controller Icons')
    window.configure(bg=BG_DARK)
    window.geometry('720x640')
    window.minsize(690, 590)

    style_engine = ttk.Style(window)
    style_engine.configure('Treeview', font=('Segoe UI', 9), rowheight=25)
    style_engine.configure('Treeview.Heading', font=('Segoe UI', 9, 'bold'))

    def make_card(parent, pady=(0, 10)):
        outer = tk.Frame(parent, bg=CARD_BG, highlightbackground=CARD_BORDER, highlightthickness=1, bd=0)
        outer.pack(fill='x', pady=pady)
        inner = tk.Frame(outer, bg=CARD_BG, padx=16, pady=12)
        inner.pack(fill='both', expand=True)
        return inner

    def make_button(parent, text, command, primary=False, padx=(8, 8), pady=5):
        bg = ACCENT if primary else SURFACE_BG
        hover_bg = ACCENT_HOVER if primary else SURFACE_HOVER
        border_col = ACCENT if primary else '#414551'
        holder = tk.Frame(parent, bg=border_col, padx=1, pady=1)
        btn = tk.Label(
            holder, text=text, bg=bg, fg=TEXT_WHITE,
            font=('Segoe UI', 9, 'bold' if primary else 'normal'),
            padx=padx[0], pady=pady, cursor='hand2',
        )
        btn.pack(fill='both', expand=True)
        btn._enabled = True

        def on_enter(e):
            if btn._enabled:
                btn.configure(bg=hover_bg)

        def on_leave(e):
            if btn._enabled:
                btn.configure(bg=bg)

        def on_click(e):
            if btn._enabled:
                command()

        def set_enabled(flag):
            btn._enabled = flag
            btn.configure(
                bg=bg if flag else '#2d3039',
                fg=TEXT_WHITE if flag else TEXT_MUTED,
                cursor='hand2' if flag else 'arrow',
            )

        def set_text(new_text):
            btn.configure(text=new_text)

        btn.bind('<Enter>', on_enter)
        btn.bind('<Leave>', on_leave)
        btn.bind('<Button-1>', on_click)
        holder.set_enabled = set_enabled
        holder.set_text = set_text
        return holder

    # Top Header
    header_wrap = tk.Frame(window, bg='#0e0f12')
    header_wrap.pack(fill='x')
    tk.Frame(header_wrap, bg=ACCENT, width=5).pack(side='left', fill='y')
    banner = tk.Frame(header_wrap, bg='#0e0f12', padx=20, pady=14)
    banner.pack(side='left', fill='both', expand=True)
    banner_top = tk.Frame(banner, bg='#0e0f12')
    banner_top.pack(fill='x')
    tk.Label(
        banner_top, text='UFC 6 Controller Icons', bg='#0e0f12', fg=TEXT_WHITE,
        font=('Segoe UI', 17, 'bold'),
    ).pack(side='left')
    tk.Label(
        banner_top, text=f'MOD v{version}', bg='#3a1720', fg='#ffd5d9',
        font=('Segoe UI', 8, 'bold'), padx=10, pady=4,
    ).pack(side='right', pady=2)
    tk.Label(
        banner, text='Title ID: PPSA23566   ·   Offline asset patcher with verified backup & rollback',
        bg='#0e0f12', fg=TEXT_MUTED, font=('Segoe UI', 9),
    ).pack(anchor='w', pady=(3, 0))

    frame = tk.Frame(window, bg=BG_DARK, padx=18, pady=14)
    frame.pack(fill='both', expand=True)

    events = queue.Queue()
    busy = [False]
    bindings = [defaults()]
    selected_style = ['xbox']
    custom_buttons = []
    tk_controls = []
    editor_state = {'window': None, 'refresh': None, 'buttons': [], 'tk_controls': [], 'tab': 'controller'}

    def append(text):
        output.configure(state='normal')
        output.insert('end', text + '\n')
        output.see('end')
        output.configure(state='disabled')

    def scan_portheon(root):
        candidates = set()
        for parent in [root, *list(root.parents)[:3], app_dir, *list(app_dir.parents)[:2]]:
            for rel in ['games/UFC6/UFC6.ini', 'PORTHEON/games/UFC6/UFC6.ini', 'UFC6.ini']:
                p = parent / rel
                if p.is_file():
                    candidates.add(p.resolve())
        if len(candidates) == 1:
            try:
                bindings[0] = load(next(iter(candidates)))
                refresh()
                append('Loaded nearby PORTHEON input settings. Use the layout editor button to review.')
            except Exception as exc:
                append('Could not import nearby settings: ' + str(exc))

    # Card 1: Extracted Game Folder
    folder_card = make_card(frame)
    tk.Label(
        folder_card, text='EXTRACTED GAME FOLDER', bg=CARD_BG, fg=TEXT_MUTED,
        font=('Segoe UI', 8, 'bold'),
    ).pack(anchor='w', pady=(0, 6))

    folder_row = tk.Frame(folder_card, bg=CARD_BG)
    folder_row.pack(fill='x')
    game = tk.StringVar()
    entry_border = tk.Frame(folder_row, bg='#414551', padx=1, pady=1)
    entry_border.pack(side='left', fill='x', expand=True, padx=(0, 10))
    field = tk.Entry(
        entry_border, textvariable=game, font=('Segoe UI', 10),
        bg=SURFACE_BG, fg=TEXT_WHITE, insertbackground=TEXT_WHITE, relief='flat', bd=5,
    )
    field.pack(fill='x')
    tk_controls.append(field)

    def choose_game():
        value = filedialog.askdirectory(parent=window, title='Choose extracted UFC 6 game folder')
        if value:
            game.set(value)
            scan_portheon(Path(value).resolve())

    browse_btn = make_button(folder_row, 'Browse…', choose_game, padx=(14, 14), pady=5)
    browse_btn.pack(side='left')
    custom_buttons.append(browse_btn)

    # Card 2: In-Game Button Icons
    selector_card = make_card(frame)
    sel_header = tk.Frame(selector_card, bg=CARD_BG)
    sel_header.pack(fill='x', pady=(0, 8))
    tk.Label(
        sel_header, text='IN-GAME BUTTON ICONS', bg=CARD_BG, fg=TEXT_MUTED,
        font=('Segoe UI', 8, 'bold'),
    ).pack(side='left')
    tk.Label(
        sel_header, text='Close UFC 6 before installing or restoring.', bg=CARD_BG, fg=TEXT_MUTED,
        font=('Segoe UI', 8),
    ).pack(side='right')

    cards_row = tk.Frame(selector_card, bg=CARD_BG)
    cards_row.pack(fill='x')

    card_widgets = {}
    card_images = {}
    card_hover = {'xbox': False, 'keyboard': False, 'playstation': False}

    def select_mode(mode):
        if busy[0]:
            return
        selected_style[0] = mode
        refresh()

    def refresh_selector_cards():
        try:
            from PIL import ImageTk
            for mode, lbl in card_widgets.items():
                im = _render_selector_card(
                    app_dir, mode,
                    selected=(selected_style[0] == mode),
                    hovered=card_hover[mode],
                    enabled=(not busy[0]),
                    binding=bindings[0],
                    width=210, height=74,
                )
                card_images[mode] = ImageTk.PhotoImage(im, master=window)
                lbl.configure(image=card_images[mode], text='')
        except ImportError:
            for mode, lbl in card_widgets.items():
                prefix = '● ' if selected_style[0] == mode else '○ '
                lbl.configure(text=prefix + mode.capitalize(), fg=TEXT_WHITE, bg=SURFACE_BG, padx=16, pady=12)

    for idx, mode in enumerate(('playstation', 'xbox', 'keyboard')):
        lbl = tk.Label(cards_row, bg=CARD_BG, bd=0, cursor='hand2')
        lbl.pack(side='left', padx=(0 if idx == 0 else 9, 0))

        def make_handlers(m):
            def on_enter(e):
                card_hover[m] = True
                refresh_selector_cards()

            def on_leave(e):
                card_hover[m] = False
                refresh_selector_cards()

            def on_click(e):
                select_mode(m)

            return on_enter, on_leave, on_click

        en, lv, cl = make_handlers(mode)
        lbl.bind('<Enter>', en)
        lbl.bind('<Leave>', lv)
        lbl.bind('<Button-1>', cl)
        card_widgets[mode] = lbl

    # Card 3: Active Layout & Preview (Adapts to Controller vs Keyboard!)
    kb_card = make_card(frame)
    kb_header = tk.Frame(kb_card, bg=CARD_BG)
    kb_header.pack(fill='x')

    kb_titles = tk.Frame(kb_header, bg=CARD_BG)
    kb_titles.pack(side='left', fill='x', expand=True)
    layout_section_title = tk.StringVar(value='XBOX CONTROLLER LAYOUT')
    tk.Label(
        kb_titles, textvariable=layout_section_title, bg=CARD_BG, fg=TEXT_MUTED,
        font=('Segoe UI', 8, 'bold'),
    ).pack(anchor='w')
    source = tk.StringVar()
    tk.Label(
        kb_titles, textvariable=source, bg=CARD_BG, fg=TEXT_WHITE,
        font=('Segoe UI', 9), wraplength=390, justify='left',
    ).pack(anchor='w', pady=(2, 0))

    kb_actions = tk.Frame(kb_header, bg=CARD_BG)
    kb_actions.pack(side='right', anchor='ne')

    def import_bindings(folder=False, parent_win=None):
        target_parent = parent_win or editor_state['window'] or window
        if folder:
            value = filedialog.askdirectory(parent=target_parent, title='Choose PORTHEON installation or UFC6 folder')
        else:
            value = filedialog.askopenfilename(
                parent=target_parent,
                title='Load UFC6.ini or Kyty keymap/launch settings',
                filetypes=[('Settings and launch files', '*.ini *.json *.txt *.cmd *.bat *.ps1 *.lnk'), ('All files', '*.*')],
            )
        if not value:
            return
        try:
            loaded = load(value)
            bindings[0] = loaded
            if loaded.custom and not loaded.has_custom_pad():
                selected_style[0] = 'keyboard'
            refresh()
            append('Bindings imported read-only. Launcher settings were not changed.')
        except Exception as exc:
            messagebox.showerror('Could not load bindings', str(exc), parent=target_parent)

    def reset_active_tab():
        if editor_state.get('tab') == 'controller':
            bindings[0] = from_pad_controls(dict(PAD_DEFAULTS), base=bindings[0], source='Kyty built-in defaults')
        else:
            bindings[0] = from_controls(dict(DEFAULTS), source='Kyty built-in defaults', extra=bindings[0].extra, custom=False)
        refresh()

    def swap_face_pair(a, b_ctrl):
        if busy[0]:
            return
        pad = bindings[0].pad_controls()
        pad[a], pad[b_ctrl] = pad.get(b_ctrl), pad.get(a)
        bindings[0] = from_pad_controls(pad, base=bindings[0])
        refresh()

    def export(parent_win=None):
        target_parent = parent_win or editor_state['window'] or window
        value = filedialog.asksaveasfilename(
            parent=target_parent,
            title='Export bindings for standalone Kyty',
            defaultextension='.json',
            filetypes=[('Binding JSON', '*.json'), ('PowerShell argument text', '*.txt')],
        )
        if value:
            try:
                if Path(value).suffix.lower() == '.txt':
                    Path(value).write_text(bindings[0].argument() + '\n', encoding='utf-8')
                else:
                    save(value, bindings[0])
                append('Exported bindings. For standalone Kyty, use the matching --keymap argument when launching.')
            except Exception as exc:
                messagebox.showerror('Export failed', str(exc), parent=target_parent)

    def copy_argument():
        value = bindings[0].argument()
        window.clipboard_clear()
        window.clipboard_append(value)
        append(
            'Copied a PowerShell-quoted Kyty --keymap argument.'
            if value else 'Built-in Kyty defaults selected: omit --keymap when launching.'
        )

    def open_layout_editor(initial_tab=None):
        tab_mode = initial_tab or ('keyboard' if selected_style[0] == 'keyboard' else 'controller')
        editor_state['tab'] = tab_mode
        existing = editor_state['window']
        if existing is not None and existing.winfo_exists():
            existing.deiconify()
            existing.lift()
            existing.focus_force()
            if editor_state['refresh']:
                editor_state['refresh']()
            return

        dlg = tk.Toplevel(window)
        dlg.title('Layout & Bindings Editor — UFC 6 Controller Icons')
        dlg.configure(bg=BG_DARK)
        dlg.geometry('800x660')
        dlg.minsize(740, 570)
        dlg.transient(window)
        editor_state['window'] = dlg

        dlg_header_wrap = tk.Frame(dlg, bg='#0e0f12')
        dlg_header_wrap.pack(fill='x')
        tk.Frame(dlg_header_wrap, bg=ACCENT, width=5).pack(side='left', fill='y')
        dlg_banner = tk.Frame(dlg_header_wrap, bg='#0e0f12', padx=20, pady=12)
        dlg_banner.pack(side='left', fill='both', expand=True)

        banner_row = tk.Frame(dlg_banner, bg='#0e0f12')
        banner_row.pack(fill='x')
        dlg_title_var = tk.StringVar()
        tk.Label(
            banner_row, textvariable=dlg_title_var, bg='#0e0f12', fg=TEXT_WHITE,
            font=('Segoe UI', 14, 'bold'),
        ).pack(side='left')

        tab_switch_frame = tk.Frame(banner_row, bg='#0e0f12')
        tab_switch_frame.pack(side='right')

        def switch_tab(new_tab):
            editor_state['tab'] = new_tab
            refresh_editor()

        tab_ctrl_btn = make_button(tab_switch_frame, 'Controller (Pad)', lambda: switch_tab('controller'), padx=(10, 10), pady=3)
        tab_ctrl_btn.pack(side='left', padx=(0, 6))
        tab_kb_btn = make_button(tab_switch_frame, 'Keyboard & Mouse', lambda: switch_tab('keyboard'), padx=(10, 10), pady=3)
        tab_kb_btn.pack(side='left')

        tk.Label(
            dlg_banner, textvariable=source, bg='#0e0f12', fg=TEXT_MUTED,
            font=('Segoe UI', 9),
        ).pack(anchor='w', pady=(2, 0))

        dlg_frame = tk.Frame(dlg, bg=BG_DARK, padx=16, pady=12)
        dlg_frame.pack(fill='both', expand=True)

        toolbar_card = make_card(dlg_frame, pady=(0, 10))
        toolbar_row = tk.Frame(toolbar_card, bg=CARD_BG)
        toolbar_row.pack(fill='x')

        dlg_buttons = [tab_ctrl_btn, tab_kb_btn]
        dlg_tk_controls = []
        toolbar_specs = [
            ('Reset defaults', reset_active_tab),
            ('Swap A↔B / ✕↔○', lambda: swap_face_pair('Cross', 'Circle')),
            ('Swap X↔Y / □↔△', lambda: swap_face_pair('Square', 'Triangle')),
            ('Load PORTHEON…', lambda: import_bindings(True, dlg)),
            ('Load INI / file…', lambda: import_bindings(False, dlg)),
            ('Export…', lambda: export(dlg)),
            ('Copy Kyty arg', copy_argument),
        ]
        for text, cmd in toolbar_specs:
            b = make_button(toolbar_row, text, cmd, padx=(8, 8), pady=4)
            b.pack(side='left', padx=(0, 5))
            dlg_buttons.append(b)

        table_outer = tk.Frame(dlg_frame, bg=CARD_BG, highlightbackground=CARD_BORDER, highlightthickness=1, bd=0)
        table_outer.pack(fill='both', expand=True, pady=(0, 10))
        table_card = tk.Frame(table_outer, bg=CARD_BG, padx=14, pady=12)
        table_card.pack(fill='both', expand=True)

        body = tk.Frame(table_card, bg=CARD_BG)
        body.pack(fill='both', expand=True)

        tree = ttk.Treeview(body, columns=('control', 'key', 'cap'), show='headings', height=11, selectmode='browse')
        tree.column('control', width=280, anchor='w')
        tree.column('key', width=250, anchor='w')
        tree.column('cap', width=150, anchor='center')
        tree.tag_configure('odd', background='#f8fafc')
        tree.tag_configure('even', background='#ffffff')

        scroll = ttk.Scrollbar(body, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side='left', fill='both', expand=True)
        scroll.pack(side='left', fill='y')

        edit_bar = tk.Frame(table_card, bg=CARD_BG)
        edit_bar.pack(fill='x', pady=(10, 4))

        selected_label = tk.StringVar(value='Select an action above to edit its binding:')
        tk.Label(edit_bar, textvariable=selected_label, bg=CARD_BG, fg=TEXT_WHITE, font=('Segoe UI', 9), width=33, anchor='w').pack(side='left')

        key_var = tk.StringVar()
        all_keys = sorted(KEY_NAMES)
        ordered_kb_keys = list(COMMON_KEYS) + [k for k in all_keys if k not in COMMON_KEYS]
        ordered_pad_keys = [f"{src} ({PAD_SOURCE_LABELS[src][0]} / {PAD_SOURCE_LABELS[src][1]})" for src in PAD_SOURCES]
        key_combo = ttk.Combobox(edit_bar, textvariable=key_var, values=ordered_kb_keys, width=24, font=('Segoe UI', 9))
        key_combo.pack(side='left', padx=(6, 8))
        dlg_tk_controls.append(key_combo)

        def apply_value(new_val):
            if busy[0]:
                return
            sel = tree.selection()
            if not sel:
                messagebox.showinfo('Select a control', 'Select a controller action in the list first.', parent=dlg)
                return
            control = sel[0]
            try:
                if editor_state['tab'] == 'controller':
                    clean_val = new_val.split(' (', 1)[0].strip() if new_val else ''
                    pad_vals = bindings[0].pad_controls()
                    pad_vals[control] = clean_val
                    bindings[0] = from_pad_controls(pad_vals, base=bindings[0])
                else:
                    values = dict(bindings[0].controls)
                    values[control] = new_val
                    bindings[0] = from_controls(values, extra=bindings[0].extra, custom=True)
                refresh()
                tree.selection_set(control)
                tree.see(control)
            except Exception as exc:
                messagebox.showerror('Invalid binding', str(exc), parent=dlg)

        def edit_modal(event=None):
            if busy[0]:
                return
            sel = tree.selection()
            if not sel:
                return
            control = sel[0]
            is_ctrl = editor_state['tab'] == 'controller'
            current_val = bindings[0].pad_controls().get(control) if is_ctrl else bindings[0].controls.get(control)
            prompt_msg = (
                f'{NAMES.get(control, control)}\nGamepad button (e.g. South, East, West, North, LeftShoulder, RightShoulder, LeftTrigger, RightTrigger, or A/B/X/Y).'
                if is_ctrl else
                f'{NAMES.get(control, control)}\nSDL key name or Mouse:Left/Right/Middle/X1/X2.\nBlank means unbound. Export changes for standalone Kyty.'
            )
            value = simpledialog.askstring(
                'Edit binding', prompt_msg,
                initialvalue=current_val or '',
                parent=dlg,
            )
            if value is None:
                return
            apply_value(value)

        def on_select(event=None):
            sel = tree.selection()
            if not sel:
                return
            control = sel[0]
            selected_label.set(f'Binding for {NAMES.get(control, control)}:')
            if editor_state['tab'] == 'controller':
                cur = bindings[0].pad_controls().get(control)
                key_var.set(f"{cur} ({PAD_SOURCE_LABELS[cur][0]} / {PAD_SOURCE_LABELS[cur][1]})" if cur in PAD_SOURCE_LABELS else (cur or ''))
            else:
                key_var.set(bindings[0].controls.get(control) or '')

        tree.bind('<<TreeviewSelect>>', on_select)
        tree.bind('<Double-1>', edit_modal)
        key_combo.bind('<Return>', lambda e: apply_value(key_var.get()))

        apply_btn = make_button(edit_bar, 'Apply', lambda: apply_value(key_var.get()), primary=True, padx=(12, 12), pady=4)
        apply_btn.pack(side='left', padx=(0, 6))
        unbind_btn = make_button(edit_bar, 'Unbind', lambda: apply_value(''), padx=(10, 10), pady=4)
        unbind_btn.pack(side='left', padx=(0, 6))
        prompt_btn = make_button(edit_bar, 'Edit dialog…', edit_modal, padx=(10, 10), pady=4)
        prompt_btn.pack(side='left')
        dlg_buttons.extend([apply_btn, unbind_btn, prompt_btn])

        tip_var = tk.StringVar()
        tk.Label(
            table_card, textvariable=tip_var,
            bg=CARD_BG, fg=TEXT_MUTED, font=('Segoe UI', 8), wraplength=720, justify='left',
        ).pack(anchor='w', pady=(4, 0))

        dlg_footer = tk.Frame(dlg_frame, bg=BG_DARK)
        dlg_footer.pack(fill='x')
        dlg_preview = tk.Label(dlg_footer, bg=BG_DARK, bd=0)
        dlg_preview.pack(side='left')
        dlg_preview_img = [None]

        done_btn = make_button(dlg_footer, 'Done', dlg.destroy, primary=True, padx=(18, 18), pady=5)
        done_btn.pack(side='right', pady=2)

        def refresh_editor():
            if not dlg.winfo_exists():
                return
            is_ctrl = editor_state['tab'] == 'controller'
            dlg_title_var.set('Controller (Pad) Layout Editor' if is_ctrl else 'Keyboard & Mouse Layout Editor')
            prev_sel = tree.selection()
            for child in tree.get_children():
                tree.delete(child)
            if is_ctrl:
                tree.heading('control', text='In-game controller action')
                tree.heading('key', text='Physical gamepad button (Pad:)')
                tree.heading('cap', text='Xbox / PlayStation icon')
                key_combo.configure(values=ordered_pad_keys)
                tip_var.set(
                    'Tip: Remapping controller buttons here updates both the in-game Xbox / PlayStation prompt icons '
                    'and the exported Kyty Pad: keymap. Reinstall icons after changing bindings.'
                )
                pad_map = bindings[0].pad_controls()
                for idx, (control, src) in enumerate(pad_map.items()):
                    tag = 'odd' if idx % 2 else 'even'
                    if src in PAD_SOURCE_LABELS:
                        xb_i, ps_i, full_lbl = PAD_SOURCE_LABELS[src]
                        icon_txt = f'Xbox {xb_i}  /  PS {ps_i}'
                    else:
                        full_lbl = src or 'UNBOUND'
                        icon_txt = '-'
                    tree.insert('', 'end', iid=control, values=(NAMES.get(control, control), full_lbl, icon_txt), tags=(tag,))
                target = prev_sel[0] if prev_sel and prev_sel[0] in pad_map else 'Cross'
            else:
                tree.heading('control', text='In-game controller action')
                tree.heading('key', text='Keyboard / mouse binding')
                tree.heading('cap', text='In-game keycap')
                key_combo.configure(values=ordered_kb_keys)
                tip_var.set(
                    'Tip: Double-click any row or use the field above (SDL key name or Mouse:Left/Right/Middle/X1/X2). '
                    'Changing controls later requires reinstalling keyboard icons.'
                )
                for idx, (control, key) in enumerate(bindings[0].controls.items()):
                    tag = 'odd' if idx % 2 else 'even'
                    tree.insert(
                        '', 'end', iid=control,
                        values=(NAMES.get(control, control), key or 'UNBOUND', keycap_label(key)),
                        tags=(tag,),
                    )
                target = prev_sel[0] if prev_sel and prev_sel[0] in bindings[0].controls else 'Cross'

            tree.selection_set(target)
            on_select()
            preview_style = (selected_style[0] if selected_style[0] in ('xbox', 'playstation') else 'xbox') if is_ctrl else 'keyboard'
            try:
                from PIL import ImageTk
                im = _render_preview(app_dir, bindings[0], style=preview_style, width=640)
                dlg_preview_img[0] = ImageTk.PhotoImage(im, master=dlg)
                dlg_preview.configure(image=dlg_preview_img[0], text='')
            except ImportError:
                dlg_preview.configure(image='', text='Install Pillow for preview', fg=TEXT_MUTED)

        editor_state['refresh'] = refresh_editor
        editor_state['buttons'] = dlg_buttons
        editor_state['tk_controls'] = dlg_tk_controls
        if busy[0]:
            for b in dlg_buttons:
                b.set_enabled(False)
            for w in dlg_tk_controls:
                w.configure(state='disabled')

        def on_close_dlg():
            editor_state['window'] = None
            editor_state['refresh'] = None
            editor_state['buttons'] = []
            editor_state['tk_controls'] = []
            dlg.destroy()

        dlg.protocol('WM_DELETE_WINDOW', on_close_dlg)
        refresh_editor()
        dlg.update_idletasks()
        avail_h = max(540, dlg.winfo_screenheight() - 100)
        while dlg.winfo_reqheight() + 16 > avail_h and int(tree.cget('height')) > 5:
            tree.configure(height=int(tree.cget('height')) - 1)
            dlg.update_idletasks()
        dlg_w = min(max(800, dlg.winfo_reqwidth() + 16), dlg.winfo_screenwidth() - 40)
        dlg_h = min(max(650, dlg.winfo_reqheight() + 16), avail_h)
        dlg.minsize(min(740, dlg_w), min(560, dlg_h))
        dlg.geometry(f'{dlg_w}x{dlg_h}')

    quick_import_btn = make_button(kb_actions, 'Import INI / keymap…', lambda: import_bindings(False), padx=(10, 10), pady=4)
    quick_import_btn.pack(side='left', padx=(0, 8))
    edit_layout_btn = make_button(kb_actions, 'Edit controller layout…', lambda: open_layout_editor(), padx=(12, 12), pady=4)
    edit_layout_btn.pack(side='left')
    custom_buttons.extend([quick_import_btn, edit_layout_btn])

    summary_var = tk.StringVar()
    tk.Label(
        kb_card, textvariable=summary_var, bg=CARD_BG, fg=TEXT_MUTED,
        font=('Segoe UI', 8), wraplength=640, justify='left',
    ).pack(anchor='w', pady=(6, 6))

    preview = tk.Label(kb_card, bg=CARD_BG, bd=0)
    preview.pack(anchor='w', pady=(2, 0))
    preview_image = [None]

    def refresh():
        mode = selected_style[0]
        if mode == 'keyboard':
            layout_section_title.set('KEYBOARD & MOUSE LAYOUT')
            edit_layout_btn.set_text('Edit keyboard layout…')
        elif mode == 'xbox':
            layout_section_title.set('XBOX CONTROLLER LAYOUT')
            edit_layout_btn.set_text('Edit controller layout…')
        else:
            layout_section_title.set('PLAYSTATION CONTROLLER LAYOUT')
            edit_layout_btn.set_text('Edit controller layout…')

        source.set('Source: ' + bindings[0].source)
        summary_var.set(_summary_text(bindings[0], mode))
        refresh_selector_cards()
        try:
            from PIL import ImageTk
            im = _render_preview(app_dir, bindings[0], style=mode, width=648)
            preview_image[0] = ImageTk.PhotoImage(im, master=window)
            preview.configure(image=preview_image[0], text='')
        except ImportError:
            preview.configure(
                image='',
                text='Install Pillow for the prompt preview: python -m pip install -r requirements.txt',
                fg=TEXT_MUTED,
            )
        if editor_state['refresh'] is not None:
            editor_state['refresh']()

    # Card 4: Actions & Status Log
    action_card = make_card(frame, pady=(0, 6))
    buttons = tk.Frame(action_card, bg=CARD_BG)
    buttons.pack(fill='x', pady=(0, 10))

    def set_all_enabled(flag):
        for b in custom_buttons:
            b.set_enabled(flag)
        for b in editor_state['buttons']:
            b.set_enabled(flag)
        for w in tk_controls:
            w.configure(state='normal' if flag else 'disabled')
        for w in editor_state['tk_controls']:
            if w.winfo_exists():
                w.configure(state='normal' if flag else 'disabled')
        refresh_selector_cards()

    def execute(action):
        if not game.get().strip():
            append('Select your extracted game folder first.')
            return
        root = game.get().strip()
        mode = selected_style[0]
        selected = bindings[0]
        busy[0] = True
        set_all_enabled(False)
        append(action.capitalize() + '…')

        def worker():
            try:
                message = input_icons.run(
                    action, root, input_icons.load_profile(app_dir),
                    lambda s: events.put(('log', s)), style=mode, bindings=selected,
                )
                events.put(('done', message))
            except Exception as exc:
                events.put(('done', 'Could not complete: ' + str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    btn_specs = [
        ('Install selected icons', 'install', True),
        ('Check status', 'status', False),
        ('Restore original', 'restore', False),
    ]
    for text, action, is_primary in btn_specs:
        b = make_button(buttons, text, lambda a=action: execute(a), primary=is_primary, padx=(14, 14), pady=5)
        b.pack(side='left', padx=(0, 8))
        custom_buttons.append(b)

    def licenses():
        from tkinter.scrolledtext import ScrolledText
        dialog = tk.Toplevel(window)
        dialog.title('Licenses & Third-Party Notices')
        dialog.configure(bg=BG_DARK)
        dialog.geometry('760x540')
        text = ScrolledText(dialog, wrap='word', font=('Consolas', 9), bg=SURFACE_BG, fg=TEXT_WHITE, insertbackground=TEXT_WHITE)
        text.pack(fill='both', expand=True, padx=12, pady=12)
        text.insert('1.0', license_text())
        text.configure(state='disabled')

    lic_btn = make_button(buttons, 'Licenses', licenses, padx=(12, 12), pady=5)
    lic_btn.pack(side='right')

    log_border = tk.Frame(action_card, bg=CARD_BORDER, padx=1, pady=1)
    log_border.pack(fill='both', expand=True)
    output = tk.Text(
        log_border, height=4, wrap='word', state='disabled',
        font=('Segoe UI', 9), bg=SURFACE_BG, fg=TEXT_WHITE, relief='flat', padx=8, pady=6,
    )
    output.pack(fill='both', expand=True)

    tk.Label(
        frame,
        text='Keep .ufc6-input-icons-backup.zip and .ufc6-input-icons-state.json in the game folder for restore and mode switching.',
        bg=BG_DARK, fg=TEXT_MUTED, font=('Segoe UI', 8), wraplength=680, justify='left',
    ).pack(anchor='w', pady=(2, 0))

    def poll():
        try:
            while True:
                kind, data = events.get_nowait()
                if kind == 'log':
                    append(data)
                else:
                    append(data)
                    busy[0] = False
                    set_all_enabled(True)
        except queue.Empty:
            pass
        window.after(75, poll)

    def close():
        if busy[0]:
            append('Wait for installation and verification to finish.')
        else:
            window.destroy()

    window.protocol('WM_DELETE_WINDOW', close)
    refresh()
    poll()
    window.update_idletasks()

    available_height = max(540, window.winfo_screenheight() - 100)
    if window.winfo_reqheight() + 16 > available_height:
        output.configure(height=3)
        window.update_idletasks()
    width = min(max(720, window.winfo_reqwidth() + 16), window.winfo_screenwidth() - 40)
    height = min(max(610, window.winfo_reqheight() + 16), available_height)
    window.minsize(min(690, width), min(560, height))
    window.geometry(f'{width}x{height}')
    window.mainloop()
