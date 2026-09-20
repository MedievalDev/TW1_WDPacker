"""Guide window of the WD Packer: Help > Guide, F1 (PY_TOOL_DESIGN.md 6.2).

Chapter tree on the left, text on the right, search on top, German and
English. The reference tables come from the constants the tool uses
(wdcore, wdio), each with a source line.
"""

import re
import tkinter as tk
from tkinter import ttk

import theme


def _lang():
    import wd_packer as M
    return M._LANG


def _l(de, en):
    return de if _lang() == 'de' else en


def _table(head, rows):
    out = ['| ' + ' | '.join(head) + ' |', '|' + '---|' * len(head)]
    for r in rows:
        out.append('| ' + ' | '.join(str(c) for c in r) + ' |')
    return '\n'.join(out)


def _source(text):
    return _l('Quelle: ', 'Source: ') + text + '\n'


def ch_start():
    keys = [('Strg+O', 'Ctrl+O', _l('WD-Archiv entpacken', 'Unpack a WD archive')),
            ('Strg+P', 'Ctrl+P', _l('Ordner zu einem WD-Archiv packen', 'Pack a folder into a WD archive')),
            ('F1', 'F1', _l('Dieser Guide', 'This guide'))]
    rows = [(k[0] if _lang() == 'de' else k[1], k[2]) for k in keys]
    return _l('''# Einstieg

Two Worlds packt fast alles in `.wd`-Archive: das Spiel in `WDFiles\\`, Mods
in `Mods\\`. Der WD Packer macht zwei Dinge:

- **Entpacken:** eine `.wd` auf das Fenster ziehen. Daneben entsteht ein
  Ordner mit demselben Namen und allen Dateien darin.
- **Packen:** einen Ordner auf das Fenster ziehen. Daneben entsteht eine
  `.wd` mit demselben Namen.

Mehr gibt es nicht zu tun. Alles, was fuer ein sauberes Zurueckpacken noetig
ist, schreibt das Tool beim Entpacken selbst mit (Kapitel "Was beim Entpacken
mitkommt"). Kern ist der WD Repacker (Python) von buglord.

''', '''# Getting started

Two Worlds keeps almost everything in `.wd` archives: the game in
`WDFiles\\`, mods in `Mods\\`. The WD Packer does two things:

- **Unpack:** drag a `.wd` onto the window. A folder with the same name and
  all files inside appears next to it.
- **Pack:** drag a folder onto the window. A `.wd` with the same name
  appears next to it.

That is all there is to do. Everything a clean repack needs is written down
by the tool while unpacking (chapter "What unpacking keeps"). The core is
buglord's WD Repacker (Python).

''') + _table([_l('Taste', 'Key'), _l('Wirkung', 'Action')], rows) + '\n' + _source('wd_packer.py, _bind_keys')


def ch_unpack():
    return _l('''# Entpacken

1. Eine `.wd` aus dem Explorer auf das Fenster ziehen, oder auf
   **WD entpacken...** klicken und eine waehlen.
2. Das Tool entpackt in einen Ordner neben der Datei, benannt wie das
   Archiv (`Yamalin.wd` wird `Yamalin`). Gibt es den Ordner schon und ist er
   nicht leer, nimmt es `Yamalin (2)` - nichts wird ueberschrieben.
3. Der Balken zeigt den Fortschritt, **Abbrechen** haelt an.
4. Am Ende steht unten, wie viele Dateien es waren, mit **Ordner oeffnen**.

Auch Archive des Spiels lassen sich entpacken, sie werden nur gelesen.
Archive von Two Worlds 2 entpackt der Kern ebenfalls.
''', '''# Unpacking

1. Drag a `.wd` from Explorer onto the window, or click **Unpack WD...** and
   pick one.
2. The tool unpacks into a folder next to the file, named like the archive
   (`Yamalin.wd` becomes `Yamalin`). If that folder exists and is not empty,
   it takes `Yamalin (2)` - nothing is overwritten.
3. The bar shows the progress, **Cancel** stops.
4. At the end the window says how many files it were, with **Open folder**.

Archives of the game can be unpacked too, they are only read. The core
unpacks Two Worlds 2 archives as well.
''')


def ch_pack():
    return _l('''# Packen

1. Den Ordner auf das Fenster ziehen, oder auf **Ordner packen...** klicken.
2. Das Tool packt in eine `.wd` neben dem Ordner, benannt wie der Ordner.
   Gibt es die schon, fragt es einmal; die alte Fassung kommt vorher in den
   Sicherungsordner des Tools.
3. Danach liest es das neue Archiv zurueck und vergleicht jede Datei mit der
   im Ordner. Erst wenn alles stimmt, ersetzt es die alte `.wd`.
4. Ins Spiel kommt die Mod ueber den Ordner `Mods\\` und den Mod Manager.

In den Ordner `WDFiles` des Spiels schreibt das Tool nicht, und nicht,
solange Two Worlds laeuft.
''', '''# Packing

1. Drag the folder onto the window, or click **Pack folder...**.
2. The tool packs into a `.wd` next to the folder, named like the folder. If
   that exists it asks once; the old version goes to the tool's backup
   folder first.
3. Then it reads the new archive back and compares every file with the one
   in the folder. Only when everything matches does it replace the old `.wd`.
4. A mod reaches the game through the `Mods\\` folder and the Mod Manager.

The tool does not write into the game's `WDFiles` folder, and not while Two
Worlds is running.
''')


def ch_keep():
    import wdcore
    rows = [('GUID', _l('Kennung des Archivs (16 Byte)', 'id of the archive (16 bytes)')),
            ('FILETIME', _l('Zeitstempel des Archivs', 'time stamp of the archive')),
            (wdcore.FLAGS_FILE, _l('Kennzeichen von Dateien, die der Kern beim Packen falsch raten wuerde',
                                   'flags of files the core would guess wrong when packing'))]
    return _l('''# Was beim Entpacken mitkommt

Im entpackten Ordner liegen neben den Dateien des Spiels bis zu drei kleine
Dateien. Sie gehoeren nicht ins Spiel; beim Packen liest das Tool sie und
packt sie nicht mit:

''', '''# What unpacking keeps

Next to the files of the game an unpacked folder holds up to three small
files. They are not game files; packing reads them and leaves them out:

''') + _table([_l('Datei', 'File'), _l('Inhalt', 'Content')], rows) + '\n\n' + _source('wdcore.py, KEEP') + _l('''
Manche Dateien (Karten `.lnd`, Skripte `.eco`, die Parameter `.par`) tragen
im Archiv Metadaten: einen Namen, eine Klassen-Id, eine GUID. Solche Dateien
beginnen nach dem Entpacken mit einem kleinen gepackten Kopf, in dem das
steht - so macht es buglords Repacker. Die Werkzeuge von Alchemy Fox (PAR
Editor, Quest Creator) lesen sie direkt. Wer eine solche Datei von Hand
aendert, laesst den Kopf stehen.

Gemessen am Spiel und an sieben Community-Mods: nach Entpacken und Packen
hat jede Datei denselben Inhalt und dieselben Metadaten wie vorher.
''', '''
Some files (maps `.lnd`, scripts `.eco`, the parameters `.par`) carry
metadata in the archive: a name, a class id, a GUID. After unpacking such
files start with a small packed header that holds it - that is how
buglord's repacker does it. The Alchemy Fox tools (PAR Editor, Quest
Creator) read them directly. Whoever edits such a file by hand leaves the
header in place.

Measured on the game and on seven community mods: after unpacking and
packing every file has the same content and the same metadata as before.
''')


def ch_reference():
    import wdio
    rows = [(', '.join(wdio._TEXT_FILES_), '0x05', _l('gepackt, Text', 'compressed, text')),
            ('.phx', '0x00', _l('ungepackt (Physik)', 'uncompressed (physics)')),
            (_l('alle anderen', 'all others'), '0x01', _l('gepackt', 'compressed')),
            (_l('Datei mit Kopf', 'file with header'), _l('aus dem Kopf', 'from the header'),
             _l('Metadaten wie im Original', 'metadata as in the original'))]
    return _l('''# Referenz

Welches Kennzeichen eine Datei beim Packen bekommt, wenn im Ordner nichts
anderes steht:

''', '''# Reference

Which flags a file gets when packing, unless the folder says otherwise:

''') + _table([_l('Endung', 'Extension'), _l('Kennzeichen', 'Flags'), _l('Bedeutung', 'Meaning')], rows) \
        + '\n\n' + _source('wdio.py (buglord), v1_chk_file / _TEXT_FILES_') + _l('''
Weicht das Original davon ab, steht die Datei in `WDFLAGS` und behaelt ihr
Kennzeichen. Das Archiv selbst: gepackter Kopf `FF A1 D0 31 'WD' 00 02` mit
GUID, dann die Daten, am Ende das gepackte Verzeichnis und seine Laenge.
''', '''
If the original differs, the file is listed in `WDFLAGS` and keeps its
flags. The archive itself: packed head `FF A1 D0 31 'WD' 00 02` with GUID,
then the data, at the end the packed directory and its length.
''')


def ch_trouble():
    return _l('''# Fehlersuche

## "Diese Namen passen nicht in eine .wd"

Das Archiv speichert Dateinamen nur in ASCII und bis 255 Zeichen. Umlaute
oder lange Pfade im Ordner umbenennen, dann noch einmal packen.

## "Two Worlds laeuft"

Das Spiel haelt seine Archive offen. Erst beenden, dann packen.

## "Pruefung fehlgeschlagen"

Eine Datei im Ordner wurde waehrend des Packens geaendert, oder der
Datentraeger hatte einen Fehler. Die alte `.wd` ist unveraendert; einfach
noch einmal packen.

## Das Packen dauert beim ersten Mal lange

Frisch entpackte Ordner mit tausenden Dateien prueft der Virenscanner beim
ersten Oeffnen jeder Datei. Gemessen an `Shaders.wd` (4784 Dateien): 36 s
beim ersten Packen, 9 s beim zweiten.
''', '''# Troubleshooting

## "These names cannot go into a .wd"

The archive stores file names only in ASCII and up to 255 characters.
Rename umlauts or long paths in the folder, then pack again.

## "Two Worlds is running"

The game keeps its archives open. Quit it first, then pack.

## "Check failed"

A file in the folder changed while packing, or the drive had an error. The
old `.wd` is unchanged; just pack again.

## Packing takes long the first time

The virus scanner checks freshly unpacked folders with thousands of files
on the first open of each file. Measured on `Shaders.wd` (4784 files): 36 s
on the first pack, 9 s on the second.
''')


CHAPTERS = (
    ('start', ('Einstieg', 'Getting started'), ch_start),
    ('unpack', ('Entpacken', 'Unpacking'), ch_unpack),
    ('pack', ('Packen', 'Packing'), ch_pack),
    ('keep', ('Was beim Entpacken mitkommt', 'What unpacking keeps'), ch_keep),
    ('reference', ('Referenz', 'Reference'), ch_reference),
    ('trouble', ('Fehlersuche', 'Troubleshooting'), ch_trouble),
)


_SEPARATOR = re.compile(r'^\|[\s|:-]+\|?$')
_LIST_ITEM = re.compile(r'^(- |\d+\. )')


def _prepare(text):
    """Join wrapped prose lines into paragraphs and turn markdown tables into
    aligned columns, so the text widget shows them readably."""
    out, para, table, in_code = [], [], [], False

    def flush_para():
        if para:
            out.append(' '.join(x.strip() for x in para))
            para.clear()

    def flush_table():
        if not table:
            return
        rows = [[c.strip().replace('`', '') for c in r.strip().strip('|').split('|')]
                for r in table if not _SEPARATOR.match(r.strip())]
        ncol = max(len(r) for r in rows)
        widths = [max(len(r[i]) if i < len(r) else 0 for r in rows) for i in range(ncol)]
        out.append('```')
        for n, r in enumerate(rows):
            cells = [(r[i] if i < len(r) else '').ljust(widths[i]) for i in range(ncol)]
            out.append('  '.join(cells).rstrip())
            if n == 0:
                out.append('  '.join('-' * w for w in widths))
        out.append('```')
        table.clear()

    for ln in text.split('\n'):
        if ln.startswith('```'):
            flush_para()
            flush_table()
            in_code = not in_code
            out.append(ln)
            continue
        if in_code:
            out.append(ln)
            continue
        if ln.startswith('|'):
            flush_para()
            table.append(ln)
            continue
        flush_table()
        stripped = ln.strip()
        if not stripped or ln.startswith('#'):
            flush_para()
            out.append(ln)
        elif _LIST_ITEM.match(stripped):
            flush_para()
            para.append(ln)
        else:
            para.append(ln)
    flush_para()
    flush_table()
    return '\n'.join(out)


def render_markdown(txt, text):
    in_code = False
    for line in text.split('\n'):
        if line.startswith('```'):
            in_code = not in_code
            continue
        if in_code or line.startswith('|'):
            txt.insert('end', line + '\n', 'code')
            continue
        m = re.match(r'(#{1,3}) (.*)', line)
        if m:
            txt.insert('end', m.group(2) + '\n', 'h%d' % len(m.group(1)))
            continue
        tag = None
        if re.match(r'\s*[-*] ', line):
            line = '• ' + re.sub(r'^\s*[-*] ', '', line)
            tag = 'li'
        elif re.match(r'\s*\d+\. ', line):
            tag = 'li'
        for part in re.split(r'(`[^`]+`|\*\*[^*]+\*\*)', line):
            if part.startswith('`') and part.endswith('`') and len(part) > 1:
                txt.insert('end', part[1:-1], ('inline',) + ((tag,) if tag else ()))
            elif part.startswith('**') and part.endswith('**'):
                txt.insert('end', part[2:-2], ('bold',) + ((tag,) if tag else ()))
            else:
                part = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', part)
                txt.insert('end', part, tag)
        txt.insert('end', '\n', tag)


def chapter_text(cid):
    for key, _title, fn in CHAPTERS:
        if key == cid:
            return fn()
    return ''


def check_sources():
    """Every table in every chapter (both languages) carries a source line."""
    import wd_packer as M
    saved = M._LANG
    try:
        for lang in ('de', 'en'):
            M._LANG = lang
            for cid, _t, fn in CHAPTERS:
                lines = fn().split('\n')
                for i, ln in enumerate(lines):
                    if ln.startswith('|---'):
                        j = i + 1
                        while j < len(lines) and lines[j].startswith('|'):
                            j += 1
                        tail = '\n'.join(lines[j:j + 3])
                        assert 'Quelle:' in tail or 'Source:' in tail, f'{cid}/{lang}: table without source'
    finally:
        M._LANG = saved


class GuideWindow:
    _open = None

    @classmethod
    def show(cls, app, chapter='start'):
        win = cls._open
        if win is not None:
            try:
                win.front()
                win.select(chapter)
                return win
            except tk.TclError:
                cls._open = None
        cls._open = cls(app, chapter)
        return cls._open

    def __init__(self, app, chapter='start'):
        self.app = app
        self.win = tk.Toplevel(app.root)
        self.win.title('WD Packer Guide')
        self.win.geometry('1000x700')
        self.win.minsize(820, 520)
        theme.dark_titlebar(self.win)
        self.win.protocol('WM_DELETE_WINDOW', self.close)
        self.win.bind('<Escape>', lambda e: self.close())
        top = ttk.Frame(self.win, padding=(10, 8))
        top.pack(fill='x')
        ttk.Label(top, text=_l('Suche', 'Search')).pack(side='left')
        self.q = tk.StringVar()
        ent = ttk.Entry(top, textvariable=self.q, width=32)
        ent.pack(side='left', padx=6)
        ent.bind('<KeyRelease>', lambda e: self._search())
        self.hits = ttk.Label(top, style='Muted.TLabel')
        self.hits.pack(side='left', padx=8)
        body = ttk.PanedWindow(self.win, orient='horizontal')
        body.pack(fill='both', expand=True)
        left = ttk.Frame(body)
        self.tree = ttk.Treeview(left, show='tree', selectmode='browse')
        self.tree.pack(fill='both', expand=True)
        self.tree.bind('<<TreeviewSelect>>', lambda e: self._show_selected())
        right = ttk.Frame(body)
        sb = ttk.Scrollbar(right, orient='vertical')
        self.txt = tk.Text(right, wrap='word', bd=0, padx=26, pady=20, cursor='arrow',
                           spacing1=2, spacing3=4, yscrollcommand=sb.set, font=('Segoe UI', 10))
        sb.configure(command=self.txt.yview)
        sb.pack(side='right', fill='y')
        self.txt.pack(fill='both', expand=True)
        for tag, kw in (('h1', dict(font=theme.FONT_H1, foreground=theme.GOLD, spacing1=18)),
                        ('h2', dict(font=theme.FONT_H2, foreground=theme.GOLD_HI, spacing1=14)),
                        ('h3', dict(font=('Segoe UI Semibold', 10), foreground=theme.GOLD_HI, spacing1=8)),
                        ('li', dict(lmargin1=20, lmargin2=34)),
                        ('code', dict(font=theme.FONT_MONO, background=theme.FIELD, lmargin1=16, lmargin2=16)),
                        ('inline', dict(font=theme.FONT_MONO, foreground=theme.GOLD_HI)),
                        ('bold', dict(font=('Segoe UI Semibold', 10))),
                        ('hit', dict(background=theme.SEL, foreground=theme.GOLD_HI))):
            self.txt.tag_configure(tag, **kw)
        body.add(left, weight=0)
        body.add(right, weight=1)
        self.win.update_idletasks()
        try:
            body.sashpos(0, 250)
        except tk.TclError:
            pass
        self._fill_tree()
        self.select(chapter)
        self.front()

    def front(self):
        """Das Fenster nach vorn holen - sonst geht es hinter dem Hauptfenster auf."""
        try:
            self.win.lift()
            self.win.focus_force()
            self.win.attributes('-topmost', True)          # einmal nach vorn,
            self.win.after(120, lambda: self.win.attributes('-topmost', False))
        except tk.TclError:                                # und gleich wieder normal
            pass

    def close(self):
        GuideWindow._open = None
        self.win.destroy()

    def _fill_tree(self, only=None):
        self.tree.delete(*self.tree.get_children())
        lang = 0 if _lang() == 'de' else 1
        for i, (cid, titles, _fn) in enumerate(CHAPTERS, start=1):
            if only is not None and cid not in only:
                continue
            self.tree.insert('', 'end', iid=cid, text=f'{i}. {titles[lang]}')

    def select(self, cid):
        if cid not in {c for c, _t, _f in CHAPTERS}:
            cid = 'start'
        if not self.tree.exists(cid):
            self._fill_tree()
        self.tree.selection_set(cid)
        self.tree.see(cid)
        self._show(cid)

    def _show_selected(self):
        sel = self.tree.selection()
        if sel:
            self._show(sel[0])

    def _show(self, cid):
        self.current = cid
        self.txt.configure(state='normal')
        self.txt.delete('1.0', 'end')
        render_markdown(self.txt, _prepare(chapter_text(cid)))
        self._mark_hits()
        self.txt.configure(state='disabled')

    def _search(self):
        needle = self.q.get().strip().lower()
        if not needle:
            self._fill_tree()
            self.hits.configure(text='')
            self.select(getattr(self, 'current', 'start'))
            return
        found = [cid for cid, _t, fn in CHAPTERS if needle in fn().lower()]
        self._fill_tree(set(found))
        self.hits.configure(text=_l('{n} Kapitel', '{n} chapters').format(n=len(found)))
        if found:
            self.select(found[0])

    def _mark_hits(self):
        needle = self.q.get().strip() if hasattr(self, 'q') else ''
        self.txt.tag_remove('hit', '1.0', 'end')
        if not needle:
            return
        first = None
        pos = '1.0'
        while True:
            pos = self.txt.search(needle, pos, nocase=True, stopindex='end')
            if not pos:
                break
            end = f'{pos}+{len(needle)}c'
            self.txt.tag_add('hit', pos, end)
            first = first or pos
            pos = end
        if first:
            self.txt.see(first)
