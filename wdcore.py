"""Unpack and pack Two Worlds .wd archives - with buglord's wdio.py as the core.

wdio.py (buglord, CC0, github.com/buglord/Two-Worlds-1-Misc-Projects,
"WD Repacker (Python)") is kept unchanged next to this file. This module
calls its functions file by file so the window can show progress and stop,
and it adds what a window needs around them:

- unpacking always keeps what repacking needs (wdio "-p"): the archive GUID
  and FILETIME as two files in the folder root, and for files with
  directory metadata (flags beyond "compressed/text") a small zlib header
  stream in front of the data - wdio reads that back when packing
- packing writes into ``<name>.wd.<pid>.wdtmp`` first, reads the result back
  and compares every entry with its source, and only then replaces the
  target; the old archive is kept in the backup folder
- names wdio cannot store (not ASCII, longer than 255 bytes) are reported
  before anything is written; paths leaving the target folder ("..", drive
  letters) are refused on unpacking

TW1 archives are version 0x200. Two Worlds 2 archives (0x301, 0x401) are
unpacked by wdio as well; packing makes TW1 archives only.
"""

import contextlib
import io
import os
import shutil
import struct
import time
import zlib

import wdio

EXT_TMP = '.wdtmp'
FLAGS_FILE = 'WDFLAGS'          # flags wdio would guess wrong: "0x01<TAB>inner path" per line
KEEP = ('GUID', 'FILETIME', FLAGS_FILE)
ZLIB_HEAD = bytes([0x78, 0x9C])
NL, TAB = chr(10), chr(9)


_wdio_ft = wdio.filetime_to_datetime


def _tolerant_ft(ft):
    """wdio turns the FILETIME into a date for display only; on Windows a time
    before 1970 (0 is common in tool-made archives) raises. The raw value is
    kept either way."""
    try:
        return _wdio_ft(ft)
    except (OSError, OverflowError, ValueError):
        return __import__('datetime').datetime(1970, 1, 1)


wdio.filetime_to_datetime = _tolerant_ft


def wdio_guess(inner, head):
    """The flags wdio.v1_chk_file gives a plain file when packing."""
    if head[:2] == ZLIB_HEAD:
        return None                   # wdio would take it for a metadata header
    ext = os.path.splitext(inner)[1]
    if ext in wdio._TEXT_FILES_:
        return 0b101
    if ext == '.phx':
        return 0
    return 0x1


class Cancelled(Exception):
    pass


def _quiet():
    return contextlib.redirect_stdout(io.StringIO())


def inspect(path):
    """{'version', 'guid', 'filetime', 'files': [{'path', 'flags', 'clen', 'rlen'}], 'size'}"""
    with open(path, 'rb') as f, _quiet():
        wd = wdio.init_wd(f)
    files = [{'path': x['FilePath'], 'flags': x.get('Flags', 0), 'clen': x.get('Compressed Length', 0),
              'rlen': x.get('Uncompressed Length', 0)} for x in wd['Files']]
    return {'version': wd['Version'], 'guid': wd.get('GUID'), 'filetime': wd.get('FILETIME'),
            'files': files, 'size': os.path.getsize(path)}


def default_folder(wd_path):
    """<name> next to the archive; <name> (2), (3) ... when that exists and is not empty."""
    base = os.path.splitext(wd_path)[0]
    cand, n = base, 2
    while os.path.isdir(cand) and os.listdir(cand):
        cand = f'{base} ({n})'
        n += 1
    return cand


def _safe(dest, inner):
    target = os.path.normpath(os.path.join(dest, inner))
    root = os.path.normpath(dest)
    if os.path.isabs(inner) or ':' in inner or not (target == root or target.startswith(root + os.sep)):
        raise ValueError(f'unsafe path in the archive: {inner}')
    return target


def unpack(path, dest, progress=None, cancel=None):
    """Unpack ``path`` into ``dest`` (created). Returns the number of files."""
    progress = progress or (lambda *a: None)
    with open(path, 'rb') as f, _quiet():
        wd = wdio.init_wd(f)
        files = wd['Files']
        for x in files:
            _safe(dest, x['FilePath'])
        os.makedirs(dest, exist_ok=True)
        with wdio.make_open(os.path.join(dest, 'GUID')) as fg:
            fg.write(wd['GUID'])
        with wdio.make_open(os.path.join(dest, 'FILETIME')) as ft:
            ft.write(struct.pack('<Q', wd['FILETIME']))
        if wd['Version'] != 1:
            progress(0, len(files), '')
            wdio.unpack_v2(f, dest, files)                 # Two Worlds 2 archives: as wdio does it
            progress(len(files), len(files), '')
            return len(files)
        keep = []
        for n, x in enumerate(files):
            if cancel and cancel():
                raise Cancelled()
            if n % 20 == 0:
                progress(n, len(files), x['FilePath'])
            fp = _safe(dest, x['FilePath'])
            flags = x['Flags']
            if flags | 0b111 == 0b111:
                wdio.write_plain(f, fp, x['Offset'], x['Compressed Length'], flags)
                with open(fp, 'rb') as g:
                    head = g.read(2)
                if wdio_guess(x['FilePath'], head) != flags:
                    keep.append(f"0x{flags:02X}{TAB}{x['FilePath']}")
            else:
                wdio.write_complex_v1(f, fp, x['Offset'], x['Compressed Length'], flags, x)
        if keep:
            with open(os.path.join(dest, FLAGS_FILE), 'w', encoding='ascii', newline=NL) as g:
                g.write(NL.join(keep) + NL)
    progress(len(files), len(files), '')
    return len(files)


def folder_files(folder):
    """[(full path, inner path)] as wdio packs them (GUID and FILETIME left out)."""
    with _quiet():
        files = wdio.get_filelist(folder)
    return [(fp, rp) for fp, rp in files if rp not in KEEP]


def read_flags(folder):
    """{inner path: flags} from WDFLAGS (written on unpacking)."""
    out = {}
    p = os.path.join(folder, FLAGS_FILE)
    if os.path.isfile(p):
        with open(p, encoding='ascii', errors='replace') as f:
            for ln in f:
                if TAB in ln:
                    fl, inner = ln.rstrip(chr(13) + NL).split(TAB, 1)
                    try:
                        out[inner] = int(fl, 16)
                    except ValueError:
                        pass
    return out


def pack_problems(folder):
    """Names wdio cannot store - reported before anything is written."""
    out = []
    for _fp, rp in folder_files(folder):
        try:
            raw = rp.encode('ascii')
        except UnicodeEncodeError:
            out.append(('not ascii', rp))
            continue
        if len(raw) > 255:
            out.append(('too long', rp))
    return out


def pack(folder, out_path, progress=None, cancel=None, backup_dir=None):
    """Pack ``folder`` into ``out_path`` (TW1, version 0x200), check it, then
    replace the target. Returns {'files', 'bytes', 'backup'}."""
    progress = progress or (lambda *a: None)
    probs = pack_problems(folder)
    if probs:
        raise ValueError('these names cannot go into a .wd: '
                         + ', '.join(f'{p} ({why})' for why, p in probs[:5]))
    files = folder_files(folder)
    if not files:
        raise ValueError('the folder is empty')
    tmp = f'{out_path}.{os.getpid()}{EXT_TMP}'
    try:
        with open(tmp, 'wb') as fs, _quiet():
            header = bytes([0xFF, 0xA1, 0xD0, 0x31, 0x57, 0x44, 0x00, 0x02])
            pg = os.path.join(folder, 'GUID')
            if os.path.exists(pg):
                with open(pg, 'rb') as fg:
                    guid = fg.read()
                header += guid if len(guid) == 16 else wdio.rand_128bit()
            else:
                header += wdio.rand_128bit()
            fs.write(zlib.compress(header))
            timestamp = wdio.datetime_to_filetime(__import__('datetime').datetime.now())
            pt = os.path.join(folder, 'FILETIME')
            if os.path.exists(pt):
                with open(pt, 'rb') as ft:
                    raw = ft.read()
                if len(raw) == 8:
                    timestamp = struct.unpack('<Q', raw)[0]
            entries = []
            fixed = read_flags(folder)
            for n, (fp, rp) in enumerate(files):
                if cancel and cancel():
                    raise Cancelled()
                if n % 20 == 0:
                    progress(n, len(files), rp)
                if rp in fixed:                 # the original flags of a plain file
                    special, flags, extra = False, fixed[rp], b''
                else:
                    special, flags, extra = wdio.v1_chk_file(fp)
                off, clen, rlen = wdio.file_to_archive(fs, fp, special, flags)
                entries.append((rp, off, clen, rlen, flags, extra, fp, special))
            d = struct.pack('<QH', timestamp, len(entries))
            for rp, off, clen, rlen, flags, extra, _fp, _sp in entries:
                pb = rp.encode('ascii')
                d += struct.pack(f'<B{len(pb)}sB3I', len(pb), pb, flags, off, clen, rlen) + extra
            cdir = zlib.compress(d)
            fs.write(cdir)
            fs.write(struct.pack('<I', len(cdir) + 4))
        progress(len(files), len(files), '')
        verify(tmp, entries, cancel)
        backup = None
        if os.path.exists(out_path):
            backup = keep_backup(out_path, backup_dir)
        os.replace(tmp, out_path)
        return {'files': len(entries), 'bytes': os.path.getsize(out_path), 'backup': backup}
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def verify(archive_path, entries, cancel=None):
    """Read the new archive back and compare every entry with its source file."""
    with open(archive_path, 'rb') as f, _quiet():
        wd = wdio.init_wd(f)
        got = {x['FilePath']: x for x in wd['Files']}
        if len(got) != len(entries):
            raise ValueError(f'check failed: {len(got)} entries in the archive, {len(entries)} files packed')
        for rp, off, clen, rlen, flags, _extra, fp, special in entries:
            if cancel and cancel():
                raise Cancelled()
            x = got.get(rp)
            if x is None or x['Offset'] != off or x['Compressed Length'] != clen or x['Flags'] != flags:
                raise ValueError(f'check failed: {rp} is not stored as written')
            f.seek(off)
            blob = f.read(clen)
            with open(fp, 'rb') as src:
                data = src.read()
            if special:
                ok = blob == data[special:special + clen]
            elif flags & 1:
                ok = zlib.decompress(blob) == data
            else:
                ok = blob == data
            if not ok or x['Uncompressed Length'] != rlen:
                raise ValueError(f'check failed: {rp} differs from the file in the folder')


def keep_backup(path, backup_dir):
    """Copy an archive that is about to be replaced; returns the copy's path."""
    if not backup_dir:
        return None
    os.makedirs(backup_dir, exist_ok=True)
    stem, ext = os.path.splitext(os.path.basename(path))
    dst = os.path.join(backup_dir, f"{stem}_{time.strftime('%Y-%m-%d_%H-%M-%S')}{ext}")
    shutil.copy2(path, dst)
    return dst


def is_archive(path):
    try:
        with open(path, 'rb') as f:
            head = f.read(64)
        if head[:2] == b'WD':
            return True
        return zlib.decompressobj().decompress(head)[4:6] == b'WD'
    except (OSError, zlib.error):
        return False
