# TW1 WD Packer

Unpacks and packs the `.wd` archives of **Two Worlds 1** (2007). Drop a
`.wd` onto the window and you get a folder; drop a folder and you get a
`.wd`. Nothing else to set.

Built on **buglord's WD Repacker (Python)**
([Two-Worlds-1-Misc-Projects](https://github.com/buglord/Two-Worlds-1-Misc-Projects/tree/main/WD%20Repacker%20(Python))),
whose `wdio.py` is included unchanged.

![License: CC0](https://img.shields.io/badge/license-CC0-green) ![Platform: Windows](https://img.shields.io/badge/platform-Windows-lightgrey)

## What it does

- **Unpack:** drop a `.wd` (or click *Unpack .wd...*). A folder with the
  same name appears next to it. An existing, non-empty folder is never
  overwritten, the tool takes `Name (2)` instead.
- **Pack:** drop a folder (or click *Pack folder...*). A `.wd` with the same
  name appears next to it. If one exists the tool asks once and keeps the
  old archive in its backup folder.
- **Checked before replacing:** a new archive is written to a temp file,
  read back and compared file by file with the folder. Only then does it
  replace the target. A cancelled or failed pack leaves the old `.wd` as it
  was.
- **Clean round trip:** unpacking keeps what packing needs - the archive
  GUID and FILETIME, the metadata header of `.lnd`/`.eco`/`.par` entries (as
  buglord's `-p` does), and in `WDFLAGS` the flags of files the packer would
  otherwise guess differently. Measured on `Update16`, `Scripts`,
  `Parameters`, `Shaders`, `Language` and seven community mods: after
  unpack + pack every entry has the same content and metadata as before.
- **Safe:** names outside ASCII or longer than 255 characters are reported
  before anything is written; paths leaving the target folder (`..`, drive
  letters) are refused; the tool never writes into the game's `WDFiles`
  folder, and does not pack into the game folder while Two Worlds runs.
- Several `.wd` files and folders can be dropped at once, they run one
  after the other. Progress bar and *Cancel*.
- **Guide inside the tool** (F1), tour on first start, gold `?` marks.
- **Test window and bug reports** to the Alchemy Fox feedback server, only
  after a preview and a button press.
- **Self-update from GitHub:** check on start (switchable), SHA-256 verified
  download.
- Dark theme, DE · EN switch, same look as the other TW1 tools.

## Files

| File | Purpose |
|---|---|
| `wd_packer.py` | the window (paths given on the command line are processed at start) |
| `wdcore.py` | unpack / pack / check around `wdio`, with progress and cancel |
| `wdio.py` | buglord's WD Repacker core, unchanged (CC0) |
| `guidebook.py` | guide window (F1), chapters DE/EN, tables from the code |
| `dropfiles.py` | drag and drop from Explorer with plain `ctypes` (`WM_DROPFILES`) |
| `theme.py`, `updater.py`, `foxfeedback*.py` | shared with the other TW1 tools |
| `tests/` | `python -m unittest discover -s tests -t .` (game archives and `Desktop\modsTW1` when present) |

Build: `build_wd_packer_exe.bat` (PyInstaller, one file), then
`selftest_exe.bat` checks the exe.

## Credits

- **buglord** - WD format research and the WD Repacker (Python) this tool is
  built on.
- Alchemy Fox / MedievalDev - window, checks, guide.

## License

CC0 1.0 Universal - see `LICENSE`. `wdio.py` is CC0 by buglord.
