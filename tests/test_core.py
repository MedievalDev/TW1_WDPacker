"""wdcore against real archives and made-up edge cases."""
import glob
import hashlib
import os
import shutil
import struct
import sys
import tempfile
import unittest
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import wdcore  # noqa: E402
import wdio  # noqa: E402

GAME = r'F:\SteamLibrary\steamapps\common\Two Worlds - Epic Edition'
MODS = os.path.join(os.path.expanduser('~'), 'Desktop', 'modsTW1')
BS = chr(92)


def entries(path):
    """{lower path: (path, flags, extra fields, data)} read independently of wdio."""
    with open(path, 'rb') as f:
        raw = f.read()
    n = struct.unpack_from('<I', raw, len(raw) - 4)[0]
    t = zlib.decompress(raw[len(raw) - n:len(raw) - 4])
    off, count, out = 10, struct.unpack_from('<H', t, 8)[0], {}
    for _ in range(count):
        ln = t[off]; off += 1
        name = t[off:off + ln].decode('latin-1'); off += ln
        flags, foff, clen, rlen = struct.unpack_from('<BIII', t, off); off += 13
        start = off
        if flags & 0x08:
            off += 1 + t[off]
        if flags & 0x10:
            off += 4
        if flags & 0x20:
            off += 16
        blob = raw[foff:foff + clen]
        data = zlib.decompress(blob) if flags & 1 else blob
        out[name.lower()] = (name, flags, t[start:off], data)
    return out


def sha(p):
    with open(p, 'rb') as f:
        return hashlib.sha1(f.read()).hexdigest()


class RealArchives(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='wdp_core_')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def roundtrip(self, src):
        before = sha(src)
        d = os.path.join(self.tmp, 'u')
        o = os.path.join(self.tmp, 'p.wd')
        shutil.rmtree(d, ignore_errors=True)
        if os.path.exists(o):
            os.remove(o)
        wdcore.unpack(src, d)
        wdcore.pack(d, o)
        a, b = entries(src), entries(o)
        self.assertEqual(set(a), set(b), src)
        for k in a:
            self.assertEqual(a[k], b[k], f'{os.path.basename(src)}: {k}')
        self.assertEqual(sha(src), before, 'source untouched')

    @unittest.skipUnless(os.path.isdir(GAME), 'game not on this PC')
    def test_game_archives(self):
        for name in ('Update16.wd', 'Scripts.wd', 'Parameters.wd', 'Language.wd', 'Content02_Lan.wd'):
            self.roundtrip(os.path.join(GAME, 'WDFiles', name))

    @unittest.skipUnless(os.path.isdir(MODS), 'community mods not on this PC')
    def test_community_mods(self):
        for p in sorted(glob.glob(os.path.join(MODS, '*.wd'))):
            self.roundtrip(p)


class Edges(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='wdp_edge_')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def p(self, *parts):
        return os.path.join(self.tmp, *parts)

    def folder(self, files):
        d = self.p('src')
        for inner, data in files.items():
            fp = os.path.join(d, *inner.split(BS))
            os.makedirs(os.path.dirname(fp), exist_ok=True)
            with open(fp, 'wb') as f:
                f.write(data)
        return d

    def test_pack_unpack_and_flags(self):
        d = self.folder({BS.join(('Scripts', 'x.qtx')): b'QUEST', 'a.phx': bytes(range(200)), 'b.dds': b'D' * 5000})
        o = self.p('m.wd')
        r = wdcore.pack(d, o)
        self.assertEqual(r['files'], 3)
        e = entries(o)
        self.assertEqual(e[BS.join(('scripts', 'x.qtx'))][1], 0x05)
        self.assertEqual(e['a.phx'][1], 0x00)
        self.assertEqual(e['b.dds'][1], 0x01)
        back = self.p('back')
        wdcore.unpack(o, back)
        with open(os.path.join(back, 'b.dds'), 'rb') as f:
            self.assertEqual(f.read(), b'D' * 5000)
        self.assertTrue(os.path.isfile(os.path.join(back, 'GUID')))

    def test_flags_file_keeps_odd_flags(self):
        # a .txt stored only compressed (0x01) - wdio would guess 0x05
        blob = zlib.compress(b'text')
        tmp = self.p('odd.wd')
        with open(tmp, 'wb') as f:
            head = zlib.compress(bytes([0xFF, 0xA1, 0xD0, 0x31, 0x57, 0x44, 0x00, 0x02]) + b'G' * 16)
            f.write(head + blob)
            name = b'readme.txt'
            d = struct.pack('<QH', 0, 1) + bytes([len(name)]) + name + struct.pack('<BIII', 0x01, len(head), len(blob), 4)
            cd = zlib.compress(d)
            f.write(cd + struct.pack('<I', len(cd) + 4))
        back = self.p('odd')
        wdcore.unpack(tmp, back)
        self.assertEqual(wdcore.read_flags(back), {'readme.txt': 0x01})
        o = self.p('odd2.wd')
        wdcore.pack(back, o)
        self.assertEqual(entries(o)['readme.txt'][1], 0x01)
        self.assertNotIn(wdcore.FLAGS_FILE.lower(), entries(o))

    def test_names_that_do_not_fit(self):
        d = self.folder({'Umlaut\u00e4.txt': b'x', 'ok.txt': b'y'})
        self.assertEqual([w for w, _p in wdcore.pack_problems(d)], ['not ascii'])
        with self.assertRaises(ValueError):
            wdcore.pack(d, self.p('bad.wd'))
        self.assertFalse(os.path.exists(self.p('bad.wd')))
        self.assertEqual([f for f in os.listdir(self.tmp) if f.endswith(wdcore.EXT_TMP)], [])

    def test_unsafe_path_is_refused(self):
        tmp = self.p('evil.wd')
        blob = zlib.compress(b'x')
        with open(tmp, 'wb') as f:
            head = zlib.compress(bytes([0xFF, 0xA1, 0xD0, 0x31, 0x57, 0x44, 0x00, 0x02]) + b'G' * 16)
            f.write(head + blob)
            name = ('..' + BS + 'evil.txt').encode()
            d = struct.pack('<QH', 0, 1) + bytes([len(name)]) + name + struct.pack('<BIII', 0x01, len(head), len(blob), 1)
            cd = zlib.compress(d)
            f.write(cd + struct.pack('<I', len(cd) + 4))
        with self.assertRaises(ValueError):
            wdcore.unpack(tmp, self.p('out'))
        self.assertFalse(os.path.exists(self.p('evil.txt')))

    def test_replace_keeps_a_backup_and_cancel_keeps_the_old(self):
        d = self.folder({'a.txt': b'one'})
        o = self.p('m.wd')
        wdcore.pack(d, o)
        old = sha(o)
        with open(os.path.join(d, 'a.txt'), 'wb') as f:
            f.write(b'two')
        with self.assertRaises(wdcore.Cancelled):
            wdcore.pack(d, o, cancel=lambda: True, backup_dir=self.p('bak'))
        self.assertEqual(sha(o), old)
        r = wdcore.pack(d, o, backup_dir=self.p('bak'))
        self.assertTrue(r['backup'] and os.path.isfile(r['backup']))
        self.assertEqual(sha(r['backup']), old)
        self.assertEqual([f for f in os.listdir(self.tmp) if f.endswith(wdcore.EXT_TMP)], [])

    def test_default_folder_never_overwrites(self):
        o = self.p('Mod.wd')
        open(o, 'wb').close()
        self.assertEqual(wdcore.default_folder(o), self.p('Mod'))
        os.makedirs(self.p('Mod'))
        open(self.p('Mod', 'x'), 'wb').close()
        self.assertEqual(wdcore.default_folder(o), self.p('Mod (2)'))

    def test_empty_folder_and_not_an_archive(self):
        os.makedirs(self.p('empty'))
        with self.assertRaises(ValueError):
            wdcore.pack(self.p('empty'), self.p('e.wd'))
        with open(self.p('no.wd'), 'wb') as f:
            f.write(b'nonsense' * 10)
        self.assertFalse(wdcore.is_archive(self.p('no.wd')))
        with self.assertRaises(Exception):
            wdcore.unpack(self.p('no.wd'), self.p('x'))

    def test_wdio_itself_packs_our_folder(self):
        """A folder unpacked here still packs with buglord's own wdio."""
        d = self.folder({'a.txt': b'hi', 'b.bin': b'B' * 100})
        o = self.p('m.wd')
        wdcore.pack(d, o)
        back = self.p('back')
        wdcore.unpack(o, back)
        o2 = self.p('by_wdio.wd')
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            wdio.pack_single(back, o2, 1, None)
        e = entries(o2)
        self.assertEqual(e['a.txt'][3], b'hi')
        self.assertEqual(e['b.bin'][3], b'B' * 100)


if __name__ == '__main__':
    unittest.main()
