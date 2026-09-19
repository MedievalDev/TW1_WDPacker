"""The window driven like a user: real WM_DROPFILES onto the drop zone,
buttons, cancel, refusals. Dialogs are stubbed, nothing is sent anywhere,
settings live in a temp folder, the window is never topmost."""
import ctypes
import os
import shutil
import sys
import tempfile
import time
import unittest
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import foxfeedback  # noqa: E402
import foxfeedback_ui  # noqa: E402
import wd_packer as M  # noqa: E402
import wdcore  # noqa: E402

WM_DROPFILES = 0x0233
_k32 = ctypes.windll.kernel32
_k32.GlobalAlloc.restype = wintypes.HGLOBAL
_k32.GlobalAlloc.argtypes = (wintypes.UINT, ctypes.c_size_t)
_k32.GlobalLock.restype = ctypes.c_void_p
_k32.GlobalLock.argtypes = (wintypes.HGLOBAL,)
_k32.GlobalUnlock.argtypes = (wintypes.HGLOBAL,)
_u32 = ctypes.windll.user32
_u32.SendMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
_u32.SendMessageW.restype = ctypes.c_ssize_t


def explorer_drop(hwnd, paths):
    """What Explorer sends: a DROPFILES block (wide names, double zero) in global memory."""
    names = (chr(0).join(paths) + chr(0) + chr(0)).encode('utf-16-le')
    head = (20).to_bytes(4, 'little') + bytes(8) + bytes(4) + (1).to_bytes(4, 'little')
    h = _k32.GlobalAlloc(0x0042, len(head) + len(names))
    p = _k32.GlobalLock(h)
    ctypes.memmove(p, head + names, len(head) + len(names))
    _k32.GlobalUnlock(h)
    _u32.SendMessageW(hwnd, WM_DROPFILES, h, 0)       # the window frees it (DragFinish)


class Window(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='wdp_ui_')
        cls._orig = (M.data_dir, M.ErrorDialog, M.messagebox.askyesno, foxfeedback.submit,
                     foxfeedback_ui.FeedbackUI.start, M.game_running)
        data = os.path.join(cls.tmp, 'data')
        os.makedirs(data)
        M.data_dir = lambda: data
        cls.errors, cls.asked = [], []
        M.ErrorDialog = lambda app, key, message, shown, guide=None, title=None: cls.errors.append((key, shown))
        M.messagebox.askyesno = lambda *a, **k: cls.asked.append(a) or True
        foxfeedback.submit = lambda *a, **k: (_ for _ in ()).throw(AssertionError('nothing is sent in tests'))
        foxfeedback_ui.FeedbackUI.start = lambda self: None
        M.game_running = lambda: False
        cfg = M.Config()
        cfg.update(guide_seen=True, update_check=False, lang='en')
        cfg.save()
        cls.app = M.App()
        cls.app.root.geometry('720x520+40+40')
        cls.app.root.lower()
        cls.pump(0.5)
        assert cls.app._drop_ok, 'drop hook not installed'

    @classmethod
    def tearDownClass(cls):
        try:
            cls.app.root.destroy()
        except Exception:
            pass
        (M.data_dir, M.ErrorDialog, M.messagebox.askyesno, foxfeedback.submit,
         foxfeedback_ui.FeedbackUI.start, M.game_running) = cls._orig
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @classmethod
    def pump(cls, secs):
        end = time.time() + secs
        while time.time() < end:
            cls.app.root.update()
            time.sleep(0.01)

    def wait_idle(self, limit=60):
        end = time.time() + limit
        self.pump(0.2)
        while (self.app.busy or self.app.jobs) and time.time() < end:
            self.pump(0.05)
        self.assertFalse(self.app.busy, 'still busy')

    def setUp(self):
        self.errors.clear()
        self.asked.clear()
        self.work = tempfile.mkdtemp(dir=self.tmp)

    def make_mod(self, name='MyMod', files=None):
        d = os.path.join(self.work, name)
        for inner, data in (files or {'Scripts/a.txt': b'hello', 'b.phx': bytes(range(256)), 'c.dds': b'D' * 3000}).items():
            fp = os.path.join(d, *inner.split('/'))
            os.makedirs(os.path.dirname(fp), exist_ok=True)
            with open(fp, 'wb') as f:
                f.write(data)
        return d

    def drop(self, *paths):
        explorer_drop(self.app.zone.winfo_id(), list(paths))
        self.wait_idle()

    def test_drop_folder_then_wd(self):
        src = self.make_mod()
        self.drop(src)
        wd = src + '.wd'
        self.assertTrue(os.path.isfile(wd))
        self.assertEqual(self.app.last_result, wd)
        self.assertIn('Packed and checked: 3 files,', self.app.lbl_result.cget('text'))
        self.assertTrue(self.app.btn_open.winfo_ismapped())
        # unpacking goes next to it; the folder is not empty, so "(2)"
        self.drop(wd)
        back = src + ' (2)'
        self.assertEqual(self.app.last_result, back)
        with open(os.path.join(back, 'Scripts', 'a.txt'), 'rb') as f:
            self.assertEqual(f.read(), b'hello')
        self.assertEqual(self.errors, [])

    def test_drop_existing_asks_and_keeps_backup(self):
        src = self.make_mod('Rep')
        self.drop(src)
        with open(os.path.join(src, 'Scripts', 'a.txt'), 'wb') as f:
            f.write(b'changed')
        self.drop(src)
        self.assertEqual(len(self.asked), 1)
        self.assertIn('The old archive is in the backup folder.', self.app.lbl_result.cget('text'))
        self.assertTrue(any(n.startswith('Rep_') for n in os.listdir(M.backup_dir())))

    def test_two_at_once_run_one_after_the_other(self):
        a, b = self.make_mod('A'), self.make_mod('B')
        self.drop(a, b)
        self.assertTrue(os.path.isfile(a + '.wd') and os.path.isfile(b + '.wd'))

    def test_wrong_things_are_refused(self):
        txt = os.path.join(self.work, 'note.txt')
        with open(txt, 'w') as f:
            f.write('x')
        self.drop(txt)
        self.assertIn('Only .wd archives and folders', self.app.statusbar.winfo_children()[0].cget('text'))
        bad = self.make_mod('Bad', {'Umlautä.txt': b'x'})
        self.drop(bad)
        self.assertEqual([k for k, _s in self.errors], ['pack.names'])
        self.assertFalse(os.path.exists(bad + '.wd'))

    def test_never_packs_into_wdfiles(self):
        game = os.path.join(self.work, 'Game')
        os.makedirs(os.path.join(game, 'WDFiles'))
        open(os.path.join(game, 'TwoWorlds.exe'), 'wb').close()
        src = self.make_mod(os.path.join('Game', 'WDFiles', 'Mine'))
        self.drop(src)
        self.assertEqual([k for k, _s in self.errors], ['pack.wdfiles'])
        self.assertFalse(os.path.exists(src + '.wd'))

    def test_cancel_leaves_the_old_archive(self):
        src = self.make_mod('Big', {f'f{i:04}.dds': os.urandom(2000) for i in range(1500)})
        self.drop(src)
        before = open(src + '.wd', 'rb').read()
        os.remove(os.path.join(src, 'f0000.dds'))
        explorer_drop(self.app.zone.winfo_id(), [src])
        end = time.time() + 10
        while not self.app.busy and time.time() < end:
            self.pump(0.01)
        self.app.cancel()
        self.wait_idle()
        self.assertIn('Cancelled', self.app.lbl_result.cget('text'))
        self.assertEqual(open(src + '.wd', 'rb').read(), before)
        self.assertEqual([f for f in os.listdir(self.work) if f.endswith(wdcore.EXT_TMP)], [])

    def test_not_an_archive_shows_an_error(self):
        p = os.path.join(self.work, 'Broken.wd')
        with open(p, 'wb') as f:
            f.write(b'nope' * 50)
        self.drop(p)
        self.assertEqual([k for k, _s in self.errors], ['unpack.failed'])
        self.assertFalse(self.app.busy)


if __name__ == '__main__':
    unittest.main()
