"""TW1 WD Packer - unpack and pack the .wd archives of Two Worlds 1.

One window, one drop zone: drop a .wd and it is unpacked into a folder next
to it; drop a folder and it is packed into a .wd next to it. The core is
buglord's WD Repacker (Python), wdio.py, used unchanged through wdcore.py.
Design after PY_TOOL_DESIGN.md.
"""

import json
import os
import queue
import subprocess
import sys
import threading
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import tkinter as tk                                   # noqa: E402
from tkinter import ttk, filedialog, messagebox        # noqa: E402

import theme                                            # noqa: E402
import guidebook                                        # noqa: E402
import updater                                          # noqa: E402
import wdcore                                           # noqa: E402
from version import VERSION                             # noqa: E402

APP_NAME = 'TW1 WD PACKER'
GITHUB_URL = 'https://github.com/MedievalDev/TW1_WDPacker'
SITE_URL = 'https://alchemy-fox.de/'
GUIDE_URL = 'https://alchemy-fox.de/game/TW1_WDPacker/'
COMMUNITY_URL = 'https://twmp.alchemy-fox.de/'
BUGLORD_URL = 'https://github.com/buglord/Two-Worlds-1-Misc-Projects'
LINKS = (('GitHub-Repo', GITHUB_URL), ('Alchemy Fox', SITE_URL),
         ('Guide-Seite', GUIDE_URL), ('Community', COMMUNITY_URL),
         ("buglord's WD Repacker", BUGLORD_URL))
GAME_EXES = ('twoworlds.exe', 'twoworldsextended.exe', 'twoworlds_radeon.exe')
SEP = chr(92)


# ------------------------------------------------------------------ Sprache --

_LANG = 'en'


def system_is_german():
    try:
        import ctypes
        return (ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF) == 0x07
    except Exception:
        return False


def tr(text):
    if _LANG == 'de':
        return DE.get(text, text)
    return text


# ------------------------------------------------------------------- Konfig --

def data_dir():
    if getattr(sys, 'frozen', False):
        d = os.path.join(os.environ.get('LOCALAPPDATA', HERE), 'TW1WDPacker')
        os.makedirs(d, exist_ok=True)
        return d
    return HERE


class Config(dict):
    def __init__(self):
        super().__init__()
        self.path = os.path.join(data_dir(), 'wd_packer_settings.json')
        try:
            with open(self.path, encoding='utf-8') as f:
                self.update(json.load(f))
        except Exception:
            pass

    def save(self):
        try:
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump(self, f, indent=2)
        except Exception:
            pass


def backup_dir():
    return os.path.join(data_dir(), 'backup')


def game_running():
    import foxfeedback_ui
    names = foxfeedback_ui.process_names()
    return bool(names) and any(n.lower() in GAME_EXES for n in names)


def game_root_of(path):
    """The Two Worlds folder ``path`` lies in (a folder with WDFiles and a game
    exe above it), or None."""
    p = os.path.abspath(path)
    while True:
        parent = os.path.dirname(p)
        if parent == p:
            return None
        if os.path.isdir(os.path.join(p, 'WDFiles')) and any(
                os.path.isfile(os.path.join(p, e)) for e in ('TwoWorlds.exe', 'TwoWorldsExtended.exe')):
            return p
        p = parent


def in_wdfiles(path):
    """True when ``path`` is inside a game's WDFiles folder - never written."""
    game = game_root_of(path)
    if not game:
        return False
    wd = os.path.normcase(os.path.join(game, 'WDFiles'))
    return os.path.normcase(os.path.abspath(path)).startswith(wd + SEP)


def help_mark(parent, text, chapter, app):
    lbl = ttk.Label(parent, text='?', foreground=theme.GOLD, cursor='hand2')
    lbl.pack(side='left', padx=(6, 0))
    theme.Tooltip(lbl, text)
    lbl.bind('<Button-1>', lambda ev: app.show_help(text, chapter))
    return lbl


def count_files(n):
    if _LANG == 'de':
        return '1 Datei' if n == 1 else f'{n} Dateien'
    return '1 file' if n == 1 else f'{n} files'


def fmt_size(n):
    if n >= 1048576:
        return f'{n / 1048576:.1f} MB'
    return f'{max(1, n // 1024)} KB'


# ------------------------------------------------------------------ Tour --

GUIDE_STEPS = [
    {'title': 'Welcome', 'widget': None, 'text':
     'This window unpacks and packs the .wd archives of Two Worlds. The core is buglord\'s '
     'WD Repacker. Nothing you already have is overwritten.'},
    {'title': 'Drop here', 'widget': 'zone', 'text':
     'Drag a .wd onto this area: a folder with its files appears next to it. Drag a folder '
     'onto it: a .wd appears next to it. Several at once work too.'},
    {'title': 'Or click', 'widget': 'buttons', 'text':
     'The two buttons do the same through a file dialog. Ctrl+O unpacks, Ctrl+P packs.'},
    {'title': 'Result', 'widget': 'result', 'text':
     'Here you see the progress and afterwards where the result is, with a button to open it. '
     'Every packed archive is read back and compared with the folder before it replaces anything.'},
    {'title': 'Help', 'widget': 'menubar', 'text':
     'F1 opens the guide. The gold ? marks jump to the matching chapter. Help also checks for updates '
     'and lets you report a bug.'},
]


class Guide:
    def __init__(self, app):
        self.app, self.i, self.frames, self.win = app, 0, [], None

    def start(self):
        self.i = 0
        if self.win:
            self.win.destroy()
        self.win = tk.Toplevel(self.app.root)
        self.win.title(tr('Tour'))
        self.win.configure(background=theme.PANEL)
        self.win.transient(self.app.root)
        self.win.protocol('WM_DELETE_WINDOW', lambda: self.finish(False))
        theme.dark_titlebar(self.win)
        f = ttk.Frame(self.win, style='Panel.TFrame', padding=14)
        f.pack(fill='both', expand=True)
        self.head = ttk.Label(f, style='PanelTitle.TLabel')
        self.head.pack(anchor='w')
        self.title = ttk.Label(f, style='Panel.TLabel', font=theme.FONT_H2, foreground=theme.GOLD)
        self.title.pack(anchor='w', pady=(4, 6))
        self.text = ttk.Label(f, style='Panel.TLabel', wraplength=340, justify='left')
        self.text.pack(anchor='w')
        self.dont = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text=tr("Don't show at startup"), variable=self.dont,
                        style='Panel.TCheckbutton').pack(anchor='w', pady=(14, 8))
        b = ttk.Frame(f, style='Panel.TFrame')
        b.pack(fill='x')
        self.back = ttk.Button(b, text=tr('Back'), command=self.prev)
        self.back.pack(side='left')
        self.next = ttk.Button(b, text=tr('Next'), style='Accent.TButton', command=self.nxt)
        self.next.pack(side='left', padx=8)
        ttk.Button(b, text=tr('Quit tour'), command=lambda: self.finish(self.dont.get())).pack(side='right')
        self.win.bind('<Escape>', lambda e: self.finish(self.dont.get()))
        self.win.bind('<Return>', lambda e: self.nxt())
        self.show()
        r = self.app.root
        self.win.geometry(f'+{r.winfo_rootx() + r.winfo_width() + 8}+{r.winfo_rooty() + 60}')

    def show(self):
        s = GUIDE_STEPS[self.i]
        self.head.configure(text=tr('Step {n} of {m}').format(n=self.i + 1, m=len(GUIDE_STEPS)))
        self.title.configure(text=tr(s['title']))
        self.text.configure(text=tr(s['text']))
        self.back.state(['!disabled'] if self.i > 0 else ['disabled'])
        self.next.configure(text=tr('Next') if self.i < len(GUIDE_STEPS) - 1 else tr('Finish'))
        self.highlight(getattr(self.app, s['widget'], None) if s['widget'] else None)

    def prev(self):
        if self.i > 0:
            self.i -= 1
            self.show()

    def nxt(self):
        if self.i < len(GUIDE_STEPS) - 1:
            self.i += 1
            self.show()
        else:
            self.finish(True)

    def highlight(self, widget):
        for f in self.frames:
            f.destroy()
        self.frames = []
        if widget is None:
            return
        root = self.app.root
        root.update_idletasks()
        x = widget.winfo_rootx() - root.winfo_rootx()
        y = widget.winfo_rooty() - root.winfo_rooty()
        w, h, t = widget.winfo_width(), widget.winfo_height(), 3
        for fx, fy, fw, fh in ((x, y, w, t), (x, y + h - t, w, t), (x, y, t, h), (x + w - t, y, t, h)):
            f = tk.Frame(root, background=theme.GOLD)
            f.place(x=fx, y=fy, width=fw, height=fh)
            self.frames.append(f)

    def finish(self, dont_show):
        self.highlight(None)
        if dont_show or self.i == len(GUIDE_STEPS) - 1:
            self.app.cfg['guide_seen'] = True
            self.app.cfg.save()
        if self.win:
            self.win.destroy()
            self.win = None


# ------------------------------------------------------------------ App --

class App:
    def __init__(self, carry=None):
        global _LANG
        self.cfg = Config()
        self._carry = carry or {}
        self.selftest = os.environ.get('WD_PACKER_SELFTEST')
        _LANG = self.cfg.get('lang') or ('de' if system_is_german() else 'en')
        self.root = tk.Tk()
        self.root.withdraw()
        theme.apply_dark_theme(self.root)
        self.root.title(f'TW1 WD Packer {VERSION}')
        self._icon()
        self.restart = False
        self.busy = False
        self.jobs = []                       # [(kind, path)] waiting
        self._cancel = False
        self._q = queue.Queue()
        self.last_result = None
        self.update_var = tk.BooleanVar(value=bool(self.cfg.get('update_check', True)))
        self.guide = Guide(self)
        self._init_feedback()
        self.build()
        self.place_window()
        self.root.deiconify()
        self.root.after(150, self._startup)

    # ---- feedback (tw1-testfenster) ----
    def _init_feedback(self):
        import foxfeedback_ui
        base = getattr(sys, '_MEIPASS', HERE)

        def cfg_set(key, value):
            self.cfg[key] = value
            self.cfg.save()
        game = self._game_dir()
        self.fb = foxfeedback_ui.FeedbackUI(
            self.root, 'wdpacker', VERSION,
            cfg_get=lambda k, d=None: self.cfg.get(k, d), cfg_set=cfg_set,
            lang=_LANG, tests_file=os.path.join(base, 'untested.json'),
            open_guide=self.show_guide, tool_name='TW1 WD Packer',
            launcher=foxfeedback_ui.tw1_launcher(game) if game else None)
        self.root.report_callback_exception = self._crash

    def _game_dir(self):
        hint = self.cfg.get('game_dir')
        if hint and os.path.isdir(os.path.join(hint, 'WDFiles')):
            return hint
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'SOFTWARE\Reality Pump\TwoWorlds') as k:
                p = winreg.QueryValueEx(k, 'DataDir')[0].rstrip(SEP)
                if os.path.isdir(os.path.join(p, 'WDFiles')):
                    return p
        except OSError:
            pass
        return None

    def _crash(self, exc, val, tb):
        import traceback
        frames = traceback.extract_tb(tb)
        mine = [f for f in frames if os.path.dirname(os.path.abspath(f.filename)) in (HERE, getattr(sys, '_MEIPASS', HERE))]
        where = mine[-1] if mine else (frames[-1] if frames else None)
        spot = f'{os.path.basename(where.filename)}:{where.lineno}' if where else '?'
        shown = ''.join(traceback.format_exception(exc, val, tb))[-3000:]
        try:
            self.fb.log.add(f'crash {exc.__name__} at {spot}')
            ErrorDialog(self, 'crash', f'{exc.__name__} at {spot}', shown, None, title='crash: ' + exc.__name__)
        except Exception:
            sys.__excepthook__(exc, val, tb)

    def error(self, key, message, shown, guide=None):
        ErrorDialog(self, key, message, shown, guide)

    def _icon(self):
        base = getattr(sys, '_MEIPASS', HERE)
        ico = os.path.join(base, 'wd_packer.ico')
        if os.path.exists(ico):
            try:
                self.root.iconbitmap(default=ico)
            except Exception:
                pass

    def place_window(self):
        if self._carry.get('geometry'):
            self.root.geometry(self._carry['geometry'])
            return
        w, h = 720, 520
        self.root.update_idletasks()
        x = max(0, (self.root.winfo_screenwidth() - w) // 2)
        y = max(0, (self.root.winfo_screenheight() - h) // 2 - 30)
        self.root.geometry(f'{w}x{h}+{x}+{y}')
        self.root.minsize(600, 460)

    # ---- start ----
    def _startup(self):
        if getattr(self, '_started', False):
            return
        self._started = True
        updater.cleanup_old()
        self.root.protocol('WM_DELETE_WINDOW', self._close)
        try:
            import dropfiles
            self._drop_ok = dropfiles.enable(self.root, self.on_drop) > 0
        except Exception:
            self._drop_ok = False
        if self.selftest:
            self._run_selftest()
            return
        for p in self._carry.get('pending') or []:
            self.on_drop([p])
        if not self._carry:
            if self.cfg.get('update_check', True):
                self.root.after(1500, self.check_updates)
            if not self.cfg.get('guide_seen'):
                self.root.after(500, self.guide.start)
            self.root.after(2500, self.fb.start)

    def _run_selftest(self):
        """Frozen build probe: pack a made-up folder, unpack it again, compare."""
        import shutil
        import tempfile
        note = ''
        tmp = tempfile.mkdtemp(prefix='wdp_selftest_')
        try:
            src = os.path.join(tmp, 'Mod')
            os.makedirs(os.path.join(src, 'Scripts'))
            with open(os.path.join(src, 'Scripts', 'a.txt'), 'wb') as f:
                f.write(b'hello')
            with open(os.path.join(src, 'b.phx'), 'wb') as f:
                f.write(bytes(range(256)))
            wdcore.pack(src, os.path.join(tmp, 'Mod.wd'))
            wdcore.unpack(os.path.join(tmp, 'Mod.wd'), os.path.join(tmp, 'back'))
            same = all(open(os.path.join(src, *p), 'rb').read() == open(os.path.join(tmp, 'back', *p), 'rb').read()
                       for p in (('Scripts', 'a.txt'), ('b.phx',)))
            note = 'roundtrip=' + ('ok' if same else 'WRONG')
        except Exception as e:
            note = f'roundtrip=failed:{type(e).__name__}:{e}'
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        https = 'ok'
        try:
            import http.client  # noqa: F401
            import ssl  # noqa: F401
            import urllib.request  # noqa: F401
        except ImportError as e:
            https = f'missing:{e.name}'
        try:
            with open(self.selftest, 'w', encoding='utf-8') as f:
                f.write(f'version={VERSION} {note} drop={self._drop_ok} chapters={len(guidebook.CHAPTERS)} '
                        f'tests={len(self.fb.tests)} https={https} frozen={getattr(sys, "frozen", False)}' + chr(10))
        finally:
            self.root.after(50, self.root.destroy)

    # ---- window ----
    def build(self):
        self.build_menubar()
        self.statusbar = ttk.Frame(self.root, style='Status.TFrame')
        self.statusbar.pack(fill='x', side='bottom')
        self.lbl_status = ttk.Label(self.statusbar, text=tr('ready'), style='Status.TLabel')
        self.lbl_status.pack(side='left')
        body = ttk.Frame(self.root, padding=(18, 14, 18, 12))
        body.pack(fill='both', expand=True)
        head = ttk.Frame(body)
        head.pack(fill='x')
        ttk.Label(head, text=tr('Unpack and pack .wd archives'), style='Brand.TLabel').pack(side='left')
        help_mark(head, tr('Drop a .wd to unpack it, drop a folder to pack it. Chapter "Getting started".'), 'start', self)

        # the one thing to use: a big drop zone (click = choose)
        self.zone = tk.Frame(body, background=theme.FIELD, highlightthickness=2,
                             highlightbackground=theme.LINE, highlightcolor=theme.GOLD, cursor='hand2')
        self.zone.pack(fill='both', expand=True, pady=(12, 10))
        inner = tk.Frame(self.zone, background=theme.FIELD)
        inner.place(relx=0.5, rely=0.5, anchor='center')
        self.zone_title = tk.Label(inner, text=tr('Drop a .wd or a folder here'), background=theme.FIELD,
                                   foreground=theme.INK, font=theme.FONT_BRAND)
        self.zone_title.pack()
        self.zone_text = tk.Label(inner, background=theme.FIELD, foreground=theme.MUT, font=theme.FONT, justify='center',
                                  text=tr('.wd  ->  a folder with its files, next to it\nfolder  ->  a .wd, next to it'))
        self.zone_text.pack(pady=(8, 0))
        for w in (self.zone, inner, self.zone_title, self.zone_text):
            w.bind('<Button-1>', lambda e: self._zone_menu(e))
            w.bind('<Enter>', lambda e: self.zone.configure(highlightbackground=theme.GOLD), add='+')
            w.bind('<Leave>', lambda e: self.zone.configure(highlightbackground=theme.LINE), add='+')

        self.buttons = ttk.Frame(body)
        self.buttons.pack(fill='x')
        self.btn_unpack = ttk.Button(self.buttons, text=tr('Unpack .wd...'), style='Accent.TButton', command=self.pick_unpack)
        self.btn_unpack.pack(side='left')
        help_mark(self.buttons, tr('Choose a .wd. It is unpacked into a folder with the same name next to it; nothing is overwritten.'), 'unpack', self)
        self.btn_pack = ttk.Button(self.buttons, text=tr('Pack folder...'), command=self.pick_pack)
        self.btn_pack.pack(side='left', padx=(18, 0))
        help_mark(self.buttons, tr('Choose a folder. It is packed into a .wd with the same name next to it, checked, and only then replaces an old one (kept as a backup).'), 'pack', self)

        self.result = ttk.Frame(body)
        self.result.pack(fill='x', pady=(12, 0))
        self.bar = ttk.Progressbar(self.result, maximum=100)
        self.lbl_result = ttk.Label(self.result, text=tr('Nothing done yet.'), style='Muted.TLabel',
                                    wraplength=640, justify='left')
        self.lbl_result.pack(fill='x')
        self.result_btns = ttk.Frame(self.result)
        self.result_btns.pack(fill='x', pady=(6, 0))
        self.btn_cancel = ttk.Button(self.result_btns, text=tr('Cancel'), command=self.cancel)
        self.btn_open = ttk.Button(self.result_btns, text=tr('Open folder'), command=self.open_result)
        self.btn_show = ttk.Button(self.result_btns, text=tr('Show in Explorer'), command=self.show_result)

    def build_menubar(self):
        bar = ttk.Frame(self.root, style='Menubar.TFrame')
        bar.pack(fill='x')
        self.menubar = bar
        for key, filler in ((tr('File'), self._fill_file), (tr('View'), self._fill_view),
                            (tr('Help'), self._fill_help)):
            item = ttk.Label(bar, text=key, style='Menubar.TLabel')
            item.pack(side='left')
            item.bind('<Button-1>', lambda ev, f=filler, w=item: self._popup(f, w))
            item.bind('<Enter>', lambda ev, w=item: w.state(['active']))
            item.bind('<Leave>', lambda ev, w=item: w.state(['!active']))
        ttk.Label(bar, text=APP_NAME, style='Menubar.TLabel').pack(side='right', padx=(0, 6))
        box = ttk.Frame(bar, style='Menubar.TFrame')
        for i, code in enumerate(('de', 'en')):
            if i:
                ttk.Label(box, text='·', style='Menubar.TLabel', padding=(2, 5)).pack(side='left')
            lbl = ttk.Label(box, text=code.upper(), style='Menubar.TLabel', padding=(4, 5), cursor='hand2',
                            foreground=theme.GOLD if code == _LANG else theme.MUT)
            lbl.pack(side='left')
            lbl.bind('<Button-1>', lambda ev, c=code: self.set_lang(c))
        box.pack(side='right', padx=(0, 10))

    def _popup(self, filler, widget):
        menu = theme.Menu(self.root)
        filler(menu)
        try:
            menu.tk_popup(widget.winfo_rootx(), widget.winfo_rooty() + widget.winfo_height())
        finally:
            menu.grab_release()

    def _zone_menu(self, ev):
        if self.busy:
            return
        m = theme.Menu(self.root)
        m.add_command(label=tr('Unpack .wd...'), command=self.pick_unpack)
        m.add_command(label=tr('Pack folder...'), command=self.pick_pack)
        try:
            m.tk_popup(ev.x_root, ev.y_root)
        finally:
            m.grab_release()

    def _fill_file(self, m):
        state = 'disabled' if self.busy else 'normal'
        m.add_command(label=tr('Unpack .wd...'), accelerator='Ctrl+O', command=self.pick_unpack, state=state)
        m.add_command(label=tr('Pack folder...'), accelerator='Ctrl+P', command=self.pick_pack, state=state)
        m.add_separator()
        m.add_command(label=tr('Open backup folder'), command=self.open_backups)
        m.add_separator()
        m.add_command(label=tr('Exit'), accelerator='Alt+F4', command=self._close)

    def _fill_view(self, m):
        sub = theme.Menu(m)
        for code, name in (('de', 'Deutsch'), ('en', 'English')):
            sub.add_radiobutton(label=name, value=code, variable=tk.StringVar(value=_LANG),
                                command=lambda c=code: self.set_lang(c))
        m.add_cascade(label=tr('Language'), menu=sub)

    def _fill_help(self, m):
        m.add_command(label=tr('Guide'), accelerator='F1', command=self.show_guide)
        m.add_command(label=tr('Start tour'), command=self.guide.start)
        m.add_command(label=tr('Documentation'), command=lambda: webbrowser.open(GUIDE_URL))
        m.add_separator()
        self.fb.add_menu_items(m)
        m.add_separator()
        for name, url in LINKS:
            m.add_command(label=f'{name}  ({url})', command=lambda u=url: webbrowser.open(u))
        m.add_separator()
        m.add_command(label=tr('Check for updates'), command=lambda: self.check_updates(manual=True))
        m.add_checkbutton(label=tr('Check for updates on start'), variable=self.update_var,
                          command=self._toggle_update_check)
        m.add_command(label=tr('Latest version on GitHub'), command=lambda: webbrowser.open(updater.LATEST_PAGE))
        m.add_separator()
        m.add_command(label=tr('About'), command=self.show_about)

    def _bind_keys(self):
        r = self.root
        r.bind('<Control-o>', lambda e: self.pick_unpack())
        r.bind('<Control-p>', lambda e: self.pick_pack())
        r.bind('<F1>', lambda e: self.show_guide())
        r.bind('<Escape>', lambda e: self.cancel() if self.busy else None)

    def status(self, text, error=False):
        self.lbl_status.configure(text=text, style='StatusErr.TLabel' if error else 'Status.TLabel')

    def show_guide(self, chapter='start'):
        guidebook.GuideWindow.show(self, chapter)

    def show_help(self, text, chapter):
        self.status(text.split(chr(10))[0][:140])
        self.show_guide(chapter)

    # ---- choosing ----
    def pick_unpack(self):
        if self.busy:
            return
        paths = filedialog.askopenfilenames(parent=self.root, title=tr('Choose .wd archives to unpack'),
                                            initialdir=self.cfg.get('last_dir') or None,
                                            filetypes=[(tr('Two Worlds archive'), '*.wd'), (tr('All files'), '*.*')])
        if paths:
            self.cfg['last_dir'] = os.path.dirname(paths[0])
            self.cfg.save()
            self.on_drop(list(paths))

    def pick_pack(self):
        if self.busy:
            return
        d = filedialog.askdirectory(parent=self.root, title=tr('Choose the folder to pack'),
                                    initialdir=self.cfg.get('last_dir') or None)
        if d:
            self.cfg['last_dir'] = os.path.dirname(os.path.normpath(d))
            self.cfg.save()
            self.on_drop([os.path.normpath(d)])

    def on_drop(self, paths):
        """.wd files are unpacked, folders packed, one after the other."""
        added, skipped = 0, 0
        for p in paths:
            p = os.path.normpath(p)
            if os.path.isdir(p):
                self.jobs.append(('pack', p))
                added += 1
            elif os.path.isfile(p) and (p.lower().endswith('.wd') or wdcore.is_archive(p)):
                self.jobs.append(('unpack', p))
                added += 1
            else:
                skipped += 1
        if skipped and not added:
            self.status(tr('Only .wd archives and folders can be dropped here.'), error=True)
        try:
            self.root.lift()
        except tk.TclError:
            pass
        self._next()

    # ---- running ----
    def _next(self):
        if self.busy or not self.jobs:
            return
        kind, path = self.jobs.pop(0)
        if kind == 'unpack':
            dest = wdcore.default_folder(path)
            self._run(kind, path, dest)
            return
        out = path.rstrip(SEP) + '.wd'
        if in_wdfiles(out):
            self.error('pack.wdfiles', 'Packing into the game folder WDFiles was refused',
                       tr('{name} would land in the game folder WDFiles. The tool never writes there - move the folder somewhere else (for example next to the Mods folder) and pack again.').format(name=os.path.basename(out)), 'pack')
            return self._next()
        if game_root_of(out) and game_running():
            self.error('pack.game.running', 'Packing into the game folder while the game runs was refused',
                       tr('Two Worlds is running. Close the game first, then pack.'), 'trouble')
            return self._next()
        probs = wdcore.pack_problems(path)
        if probs:
            self.error('pack.names', 'Some file names cannot go into a .wd',
                       tr('These names cannot go into a .wd (only ASCII, at most 255 characters):') + chr(10) + chr(10)
                       + chr(10).join(f'  {p}' for _w, p in probs[:20]), 'trouble')
            return self._next()
        if os.path.exists(out) and not messagebox.askyesno(
                APP_NAME, tr('{name} exists already.\n\nReplace it? The old archive is kept in the backup folder.').format(
                    name=os.path.basename(out)), parent=self.root):
            self.status(tr('Nothing packed.'))
            return self._next()
        self._run(kind, path, out)

    def _run(self, kind, src, dst):
        self.busy = True
        self._cancel = False
        self.last_result = None
        self.btn_unpack.state(['disabled'])
        self.btn_pack.state(['disabled'])
        self.btn_open.pack_forget()
        self.btn_show.pack_forget()
        self.bar.configure(value=0)
        self.bar.pack(fill='x', pady=(0, 6), before=self.lbl_result)
        self.btn_cancel.pack(side='right')
        what = tr('Unpacking {name} ...') if kind == 'unpack' else tr('Packing {name} ...')
        self.lbl_result.configure(text=what.format(name=os.path.basename(src)), foreground=theme.INK)
        self.fb.log.add(f'{kind} started')
        q = self._q

        def progress(done, total, name):
            q.put(('p', done, total, name))

        def work():
            try:
                if kind == 'unpack':
                    n = wdcore.unpack(src, dst, progress, lambda: self._cancel)
                    q.put(('done', {'files': n}))
                else:
                    q.put(('done', wdcore.pack(src, dst, progress, lambda: self._cancel, backup_dir())))
            except wdcore.Cancelled:
                q.put(('cancelled', None))
            except Exception as e:
                q.put(('err', e))
        threading.Thread(target=work, daemon=True).start()
        self.root.after(80, lambda: self._poll(kind, src, dst))

    def _poll(self, kind, src, dst):
        last, end = None, None
        while True:
            try:
                msg = self._q.get_nowait()
            except queue.Empty:
                break
            if msg[0] == 'p':
                last = msg
            else:
                end = msg
        if last:
            _p, done, total, name = last
            self.bar.configure(value=100 * done / max(1, total))
            self.status(tr('{done} of {total} files').format(done=done, total=total) + ('  ' + name if name else ''))
        if end is None:
            self.root.after(80, lambda: self._poll(kind, src, dst))
            return
        self.busy = False
        self.btn_unpack.state(['!disabled'])
        self.btn_pack.state(['!disabled'])
        self.btn_cancel.pack_forget()
        self.bar.pack_forget()
        if end[0] == 'done':
            res = end[1]
            self.last_result = dst
            if kind == 'unpack':
                text = tr('Unpacked: {n} from {src}\ninto {dst}').format(n=count_files(res['files']), src=os.path.basename(src), dst=dst)
                self.btn_open.configure(text=tr('Open folder'))
            else:
                text = tr('Packed and checked: {n}, {size}\n{dst}').format(n=count_files(res['files']), size=fmt_size(res['bytes']), dst=dst)
                if res.get('backup'):
                    text += chr(10) + tr('The old archive is in the backup folder.')
                self.btn_open.configure(text=tr('Open containing folder'))
            self.lbl_result.configure(text=text, foreground=theme.OK)
            self.btn_open.pack(side='left')
            self.btn_show.pack(side='left', padx=6)
            self.status(tr('Done.'))
            self.fb.log.add(f'{kind} done')
        elif end[0] == 'cancelled':
            self.lbl_result.configure(text=tr('Cancelled. Files already unpacked stay in the folder; a cancelled pack leaves the old archive unchanged.'),
                                      foreground=theme.MUT)
            self.status(tr('Cancelled.'))
            self.fb.log.add(f'{kind} cancelled')
        else:
            e = end[1]
            self.lbl_result.configure(text=tr('Failed - see the message.'), foreground=theme.ERR)
            self.fb.log.add(f'{kind} failed: {type(e).__name__}')
            if kind == 'unpack':
                self.error('unpack.failed', 'Unpacking a .wd archive failed',
                           tr('Unpacking {name} failed:\n{e}').format(name=os.path.basename(src), e=e), 'unpack')
            else:
                self.error('pack.failed', 'Packing a folder into a .wd failed',
                           tr('Packing {name} failed, nothing was replaced:\n{e}').format(name=os.path.basename(src), e=e), 'pack')
        self._next()

    def cancel(self):
        if self.busy:
            self._cancel = True
            self.jobs.clear()
            self.status(tr('Stopping ...'))

    def open_result(self):
        p = self.last_result
        if not p:
            return
        folder = p if os.path.isdir(p) else os.path.dirname(p)
        if os.path.isdir(folder):
            os.startfile(folder)

    def show_result(self):
        p = self.last_result
        if p and os.path.exists(p):
            subprocess.Popen(['explorer', '/select,', p])

    def open_backups(self):
        d = backup_dir()
        os.makedirs(d, exist_ok=True)
        os.startfile(d)

    # ---- language / close ----
    def _close(self):
        if self.busy and not messagebox.askyesno(APP_NAME, tr('Still working. Stop and close? A pack that is stopped leaves the old archive unchanged.'), parent=self.root):
            return
        self._cancel = True
        self.root.destroy()

    def set_lang(self, code):
        global _LANG
        if code == _LANG:
            return
        if self.busy:
            self.status(tr('Wait until the work is done.'), error=True)
            return
        self.cfg['lang'] = code
        self.cfg.save()
        _LANG = code
        self.restart = True
        self.carry_out = {'geometry': self.root.geometry()}
        self.root.destroy()

    # ---- updates / about ----
    def _toggle_update_check(self):
        self.cfg['update_check'] = bool(self.update_var.get())
        self.cfg.save()

    def check_updates(self, manual=False):
        results = []
        updater.check_async(lambda info, err: results.append((info, err)))

        def poll():
            try:
                if not self.root.winfo_exists():
                    return
            except tk.TclError:
                return
            if not results:
                self.root.after(200, poll)
                return
            info, err = results[0]
            if err is not None or info is None:
                if manual:
                    messagebox.showwarning(tr('Update'), tr('GitHub was not reachable: {err}').format(err=err), parent=self.root)
                return
            if not updater.is_newer(info['tag']):
                if manual:
                    messagebox.showinfo(tr('Update'), tr('You have the latest version ({version}).').format(version=VERSION), parent=self.root)
                return
            if not manual and self.cfg.get('update_skip') == info['tag']:
                return
            UpdateWindow(self, info)
        self.root.after(200, poll)

    def show_about(self):
        win = tk.Toplevel(self.root)
        win.title(tr('About'))
        win.configure(background=theme.BG)
        win.transient(self.root)
        theme.dark_titlebar(win)
        win.bind('<Escape>', lambda e: win.destroy())
        f = ttk.Frame(win, padding=16)
        f.pack(fill='both', expand=True)
        ttk.Label(f, text=f'TW1 WD Packer {VERSION}', style='Brand.TLabel').pack(anchor='w')
        ttk.Label(f, text=tr("Unpacks and packs the .wd archives of Two Worlds 1.\nCore: buglord's WD Repacker (Python), CC0, used unchanged."),
                  style='Muted.TLabel', justify='left').pack(anchor='w', pady=(6, 10))
        for name, url in LINKS:
            lnk = ttk.Label(f, text=f'{name}: {url}', style='Link.TLabel', cursor='hand2')
            lnk.pack(anchor='w', padx=(12, 0))
            lnk.bind('<Button-1>', lambda e, u=url: webbrowser.open(u))
        ttk.Button(f, text=tr('Close'), command=win.destroy).pack(anchor='e', pady=(12, 0))

    def run(self):
        self._bind_keys()
        self.root.mainloop()


class ErrorDialog:
    """An error the user can report: message, OK, "Report a bug", optional guide."""

    def __init__(self, app, key, message, shown, guide=None, title=None):
        self.win = win = tk.Toplevel(app.root)
        win.title(tr('Error'))
        win.transient(app.root)
        theme.dark_titlebar(win)
        win.bind('<Escape>', lambda e: win.destroy())
        win.bind('<Return>', lambda e: win.destroy())
        f = ttk.Frame(win, padding=16)
        f.pack(fill='both', expand=True)
        box = tk.Text(f, wrap='word', height=min(14, max(3, shown.count(chr(10)) + 2 + len(shown) // 80)),
                      width=76, background=theme.FIELD, foreground=theme.INK, relief='flat', font=theme.FONT_MONO,
                      highlightthickness=0, padx=8, pady=6)
        box.insert('1.0', shown)
        box.configure(state='disabled')
        box.pack(fill='both', expand=True)
        btns = ttk.Frame(f)
        btns.pack(fill='x', pady=(12, 0))
        ttk.Button(btns, text='OK', style='Accent.TButton', command=win.destroy).pack(side='right')
        ttk.Button(btns, text=tr('Report a bug...'),
                   command=lambda: app.fb.report_bug(parent=win, error_text=shown, error_key=key,
                                                     title=title or f'{key}: {message}', fp_text=message)
                   ).pack(side='right', padx=6)
        if guide:
            ttk.Button(btns, text=tr('Read in the guide'), command=lambda: app.show_guide(guide)).pack(side='left')
        win.update_idletasks()
        win.geometry(f'+{app.root.winfo_rootx() + 40}+{app.root.winfo_rooty() + 60}')
        win.focus_set()


class UpdateWindow:
    """A newer release exists: notes, update now, later, skip (design 9)."""

    def __init__(self, app, info):
        self.app = app
        self.info = info
        self.win = tk.Toplevel(app.root)
        self.win.title(tr('Update'))
        self.win.transient(app.root)
        self.win.geometry('620x480')
        theme.dark_titlebar(self.win)
        self.win.bind('<Escape>', lambda e: self.win.destroy())
        f = ttk.Frame(self.win, padding=16)
        f.pack(fill='both', expand=True)
        ttk.Label(f, text=tr('Version {version} is out').format(version=info['version']), style='Brand.TLabel').pack(anchor='w')
        n = len(app.fb.untested())
        extra = ('  ' + tr('{n} new thing(s) wait for testers (Help > Test what is untested).').format(n=n)) if n else ''
        ttk.Label(f, text=tr('You have {current}. The update downloads the exe from GitHub, checks its SHA-256 checksum, closes the tool and starts version {version}. The old exe stays as .old until the next start.').format(current=VERSION, version=info['version']) + extra,
                  style='Muted.TLabel', wraplength=580, justify='left').pack(anchor='w', pady=(2, 8))
        txt = tk.Text(f, wrap='word', font=theme.FONT, height=12)
        txt.pack(fill='both', expand=True)
        txt.insert('1.0', info['notes'].split(chr(10) + '---')[0].strip() or info['page'])
        txt.configure(state='disabled')
        self.status = ttk.Label(f, text='', style='Muted.TLabel', wraplength=580, justify='left')
        self.status.pack(anchor='w', pady=(8, 0))
        self.bar = ttk.Progressbar(f, maximum=100)
        btns = ttk.Frame(f)
        btns.pack(fill='x', side='bottom', pady=(10, 0))
        ttk.Button(btns, text=tr('Later'), command=self.win.destroy).pack(side='right')
        ttk.Button(btns, text=tr('Skip this version'), command=self.skip).pack(side='right', padx=6)
        self.exe = updater.frozen_exe()
        self.go = ttk.Button(btns, text=tr('Update now') if self.exe else tr('Open release page'),
                             style='Accent.TButton', command=self.start)
        self.go.pack(side='right')
        ttk.Button(btns, text=tr('View on GitHub'), command=lambda: webbrowser.open(info['page'])).pack(side='left')
        if self.exe and not info.get('sha256'):
            self.status.configure(text=tr('This release has no checksum. Without one the tool installs nothing; Update now opens the release page.'))

    def skip(self):
        self.app.cfg['update_skip'] = self.info['tag']
        self.app.cfg.save()
        self.win.destroy()

    def start(self):
        if not self.exe or not self.info.get('sha256') or not self.info.get('url'):
            webbrowser.open(self.info['page'])
            if not self.exe:
                self.win.destroy()
            return
        if self.app.busy:
            self.status.configure(text=tr('Wait until the work is done.'))
            return
        self.go.state(['disabled'])
        self.bar.pack(fill='x', pady=(6, 0), before=self.status)
        self.status.configure(text=tr('Downloading ...'))
        new = self.exe + '.new'
        state = {}

        def progress(done, total):
            state['p'] = (done, total)

        def work():
            try:
                updater.download(self.info, new, progress)
                state['ok'] = True
            except Exception as e:
                state['err'] = e
        threading.Thread(target=work, daemon=True).start()

        def poll():
            try:
                if not self.win.winfo_exists():
                    return
            except tk.TclError:
                return
            done, total = state.get('p', (0, 0))
            if total:
                self.bar.configure(value=100 * done / total)
                self.status.configure(text=tr('Downloading {done} of {total} MB ...').format(done=done // 1048576, total=max(1, total // 1048576)))
            if 'err' in state:
                self.go.state(['!disabled'])
                self.status.configure(text=tr('Update failed, nothing was changed: {err}').format(err=state['err']))
                return
            if not state.get('ok'):
                self.win.after(150, poll)
                return
            self.status.configure(text=tr('Checksum matches. The tool closes and starts the new version.'))
            try:
                updater.start_swap(self.exe, new)
            except OSError as e:
                self.status.configure(text=tr('Update failed, nothing was changed: {err}').format(err=e))
                self.go.state(['!disabled'])
                return
            self.app.root.after(300, self.app.root.destroy)
        self.win.after(150, poll)


# ------------------------------------------------------------------ Deutsch --

DE = {
    'Welcome': 'Willkommen', 'Drop here': 'Hier ablegen', 'Or click': 'Oder klicken', 'Result': 'Ergebnis', 'Help': 'Hilfe',
    "This window unpacks and packs the .wd archives of Two Worlds. The core is buglord's WD Repacker. Nothing you already have is overwritten.":
        'Dieses Fenster entpackt und packt die .wd-Archive von Two Worlds. Der Kern ist buglords WD Repacker. Nichts, was du schon hast, wird ueberschrieben.',
    'Drag a .wd onto this area: a folder with its files appears next to it. Drag a folder onto it: a .wd appears next to it. Several at once work too.':
        'Eine .wd auf diese Flaeche ziehen: daneben entsteht ein Ordner mit ihren Dateien. Einen Ordner darauf ziehen: daneben entsteht eine .wd. Mehrere auf einmal gehen auch.',
    'The two buttons do the same through a file dialog. Ctrl+O unpacks, Ctrl+P packs.':
        'Die beiden Knoepfe machen dasselbe ueber einen Dateidialog. Strg+O entpackt, Strg+P packt.',
    'Here you see the progress and afterwards where the result is, with a button to open it. Every packed archive is read back and compared with the folder before it replaces anything.':
        'Hier siehst du den Fortschritt und danach, wo das Ergebnis liegt, mit einem Knopf zum Oeffnen. Jedes gepackte Archiv wird zurueckgelesen und mit dem Ordner verglichen, bevor es etwas ersetzt.',
    'F1 opens the guide. The gold ? marks jump to the matching chapter. Help also checks for updates and lets you report a bug.':
        'F1 oeffnet den Guide. Die goldenen ? springen ins passende Kapitel. Unter Hilfe gibt es auch die Update-Pruefung und Bug melden.',
    'Tour': 'Rundgang', "Don't show at startup": 'Beim Start nicht mehr zeigen', 'Back': 'Zurueck', 'Next': 'Weiter',
    'Quit tour': 'Rundgang beenden', 'Step {n} of {m}': 'Schritt {n} von {m}', 'Finish': 'Fertig',
    'ready': 'bereit', 'Unpack and pack .wd archives': '.wd-Archive entpacken und packen',
    'Drop a .wd to unpack it, drop a folder to pack it. Chapter "Getting started".':
        'Eine .wd ablegen entpackt sie, einen Ordner ablegen packt ihn. Kapitel "Einstieg".',
    'Drop a .wd or a folder here': 'Hier eine .wd oder einen Ordner ablegen',
    '.wd  ->  a folder with its files, next to it\nfolder  ->  a .wd, next to it':
        '.wd  ->  ein Ordner mit ihren Dateien, daneben\nOrdner  ->  eine .wd, daneben',
    'Unpack .wd...': 'WD entpacken...', 'Pack folder...': 'Ordner packen...',
    'Choose a .wd. It is unpacked into a folder with the same name next to it; nothing is overwritten.':
        'Eine .wd waehlen. Sie wird in einen gleichnamigen Ordner daneben entpackt; nichts wird ueberschrieben.',
    'Choose a folder. It is packed into a .wd with the same name next to it, checked, and only then replaces an old one (kept as a backup).':
        'Einen Ordner waehlen. Er wird in eine gleichnamige .wd daneben gepackt, geprueft und ersetzt erst dann eine alte (die als Sicherung bleibt).',
    'Nothing done yet.': 'Noch nichts getan.', 'Cancel': 'Abbrechen', 'Open folder': 'Ordner oeffnen',
    'Show in Explorer': 'Im Explorer zeigen', 'File': 'Datei', 'View': 'Ansicht',
    'Open backup folder': 'Sicherungsordner oeffnen', 'Exit': 'Beenden', 'Language': 'Sprache', 'Guide': 'Guide',
    'Start tour': 'Rundgang starten', 'Documentation': 'Dokumentation', 'Check for updates': 'Nach Updates suchen',
    'Check for updates on start': 'Beim Start nach Updates suchen', 'Latest version on GitHub': 'Neueste Version auf GitHub',
    'About': 'Ueber', 'Choose .wd archives to unpack': '.wd-Archive zum Entpacken waehlen',
    'Two Worlds archive': 'Two-Worlds-Archiv', 'All files': 'Alle Dateien', 'Choose the folder to pack': 'Ordner zum Packen waehlen',
    'Only .wd archives and folders can be dropped here.': 'Hier lassen sich nur .wd-Archive und Ordner ablegen.',
    '{name} would land in the game folder WDFiles. The tool never writes there - move the folder somewhere else (for example next to the Mods folder) and pack again.':
        '{name} wuerde im Spielordner WDFiles landen. Dorthin schreibt das Tool nie - den Ordner woanders hin legen (zum Beispiel neben den Mods-Ordner) und noch einmal packen.',
    'Two Worlds is running. Close the game first, then pack.': 'Two Worlds laeuft. Erst das Spiel schliessen, dann packen.',
    'These names cannot go into a .wd (only ASCII, at most 255 characters):':
        'Diese Namen passen nicht in eine .wd (nur ASCII, hoechstens 255 Zeichen):',
    '{name} exists already.\n\nReplace it? The old archive is kept in the backup folder.':
        '{name} gibt es schon.\n\nErsetzen? Das alte Archiv bleibt im Sicherungsordner.',
    'Nothing packed.': 'Nichts gepackt.', 'Unpacking {name} ...': 'Entpacke {name} ...', 'Packing {name} ...': 'Packe {name} ...',
    '{done} of {total} files': '{done} von {total} Dateien',
    'Unpacked: {n} from {src}\ninto {dst}': 'Entpackt: {n} aus {src}\nnach {dst}',
    'Packed and checked: {n}, {size}\n{dst}': 'Gepackt und geprueft: {n}, {size}\n{dst}',
    'The old archive is in the backup folder.': 'Das alte Archiv liegt im Sicherungsordner.',
    'Open containing folder': 'Ordner oeffnen', 'Done.': 'Fertig.',
    'Cancelled. Files already unpacked stay in the folder; a cancelled pack leaves the old archive unchanged.':
        'Abgebrochen. Schon entpackte Dateien bleiben im Ordner; ein abgebrochenes Packen laesst das alte Archiv unveraendert.',
    'Cancelled.': 'Abgebrochen.', 'Failed - see the message.': 'Fehlgeschlagen - siehe Meldung.',
    'Unpacking {name} failed:\n{e}': 'Entpacken von {name} fehlgeschlagen:\n{e}',
    'Packing {name} failed, nothing was replaced:\n{e}': 'Packen von {name} fehlgeschlagen, nichts wurde ersetzt:\n{e}',
    'Stopping ...': 'Halte an ...',
    'Still working. Stop and close? A pack that is stopped leaves the old archive unchanged.':
        'Noch bei der Arbeit. Anhalten und schliessen? Ein angehaltenes Packen laesst das alte Archiv unveraendert.',
    'Wait until the work is done.': 'Warte, bis die Arbeit fertig ist.',
    'Update': 'Update', 'GitHub was not reachable: {err}': 'GitHub war nicht erreichbar: {err}',
    'You have the latest version ({version}).': 'Du hast die neueste Version ({version}).',
    "Unpacks and packs the .wd archives of Two Worlds 1.\nCore: buglord's WD Repacker (Python), CC0, used unchanged.":
        'Entpackt und packt die .wd-Archive von Two Worlds 1.\nKern: buglords WD Repacker (Python), CC0, unveraendert verwendet.',
    'Close': 'Schliessen', 'Error': 'Fehler', 'Report a bug...': 'Bug melden...', 'Read in the guide': 'Im Guide nachlesen',
    'Version {version} is out': 'Version {version} ist da',
    '{n} new thing(s) wait for testers (Help > Test what is untested).': '{n} Neuerung(en) warten auf Tester (Hilfe > Ungetestetes testen).',
    'You have {current}. The update downloads the exe from GitHub, checks its SHA-256 checksum, closes the tool and starts version {version}. The old exe stays as .old until the next start.':
        'Du hast {current}. Das Update laedt die Exe von GitHub, prueft ihre SHA-256-Pruefsumme, schliesst das Tool und startet Version {version}. Die alte Exe bleibt bis zum naechsten Start als .old liegen.',
    'Later': 'Spaeter', 'Skip this version': 'Diese Version ueberspringen', 'Update now': 'Jetzt aktualisieren',
    'Open release page': 'Release-Seite oeffnen', 'View on GitHub': 'Auf GitHub ansehen',
    'This release has no checksum. Without one the tool installs nothing; Update now opens the release page.':
        'Dieses Release hat keine Pruefsumme. Ohne sie installiert das Tool nichts; Jetzt aktualisieren oeffnet die Release-Seite.',
    'Downloading ...': 'Lade herunter ...', 'Downloading {done} of {total} MB ...': 'Lade {done} von {total} MB ...',
    'Update failed, nothing was changed: {err}': 'Update fehlgeschlagen, nichts wurde geaendert: {err}',
    'Checksum matches. The tool closes and starts the new version.': 'Pruefsumme stimmt. Das Tool schliesst sich und startet die neue Version.',
}


def _check_translations():
    import re
    guidebook.check_sources()
    for k, v in DE.items():
        assert set(re.findall(r'\{\w+\}', k)) == set(re.findall(r'\{\w+\}', v)), k
    for s in GUIDE_STEPS:
        assert s['text'] in DE and s['title'] in DE, s['title']


def run_gui(pending=None):
    carry = {'pending': pending} if pending else None
    while True:
        app = App(carry)
        app.run()
        if not app.restart:
            break
        carry = getattr(app, 'carry_out', None) or {}


if __name__ == '__main__':
    _check_translations()
    run_gui([a for a in sys.argv[1:] if os.path.exists(a)])
