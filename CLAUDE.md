# Otterly Screenshots

**Claude:** Always read this file first when working on this project. **Update this CLAUDE.md proactively:**
- After every feature implementation or bug fix
- After debugging sessions
- After any design decisions or workarounds
- When switching focus areas
- At the end of every work session — do not wait to be asked

## Project Type
**Python 3 + PyQt6** - single-file Python application

## How to Run
Double-click `OtterlyScreenshots.vbs` or run:
```
python screenshot_tool_pyqt.py
```

## Main Files
- `screenshot_tool_pyqt.py` - Main application (PyQt6 GUI, ~2900 lines)
- `screenshot_tool.py` - Legacy tkinter version (~3500 lines)

## Key Dependencies
- **PyQt6** - GUI framework
- PIL/Pillow - image handling and editing
- keyboard - global hotkeys
- mss - screen capture
- pyautogui - window management and paste automation
- pywin32 (win32gui, win32clipboard, win32con) - Windows API integration
- pyvda - virtual desktop pinning (optional but recommended)

### Text Search (OCR)
- Tesseract OCR installed at `C:\Program Files\Tesseract-OCR\tesseract.exe` via winget
- pytesseract installed for Python 3.14
- `OcrIndex` class: SQLite DB at `{save_dir}/ocr_index.db`, stores filepath + extracted text
- `OcrWorker` (QThread): runs after every new capture in background, no UI delay
- `ReindexWorker` (QThread): bulk-indexes all existing PNGs, triggered from Settings
- Search bar above gallery: filters thumbnails live as you type (all-words match)
- Result count shown inline next to search box
- `OCR_AVAILABLE` flag guards all OCR paths gracefully if Tesseract missing

### Capture Methods
- **Region Capture** (Ctrl+Shift+R) - Select area to capture
- **Full Screen Capture** (Ctrl+Shift+S) - Capture entire screen
- **Window Capture** (Ctrl+Shift+W) - Click to select window

### Organization
- **Folder system** - Create/rename/delete folders to organize screenshots
- **Folder previews** - Each folder shows 3 thumbnail previews of recent images
- **Drag-and-drop** - Drag screenshots between folders
- **Storage management** - View folder sizes and delete old screenshots

### Editing
- **Highlight tool** - Add colored highlights (yellow, green, blue, red) before saving
- **Edit existing** - Open saved screenshots in editor to add highlights

### Workflow
- **Silent capture mode** - Capture without showing main window
- **Toast notifications** - Bottom-right popup shows saved confirmation with thumbnail
- **Auto-send** - Automatically send to configured apps (VSCode Claude, etc.)
- **Send to** - Right-click context menu to send screenshots to predefined apps
- **Import/Paste** - Import from file or paste from clipboard
- **Copy to clipboard** - All captures automatically copied
- **Rapid capture** - Take multiple screenshots in succession without interruption
- **Pin to all desktops** - Window appears on all virtual desktops (via pyvda)

### Gallery
- **Context menu** - Right-click thumbnails for Open, Edit, Copy, Send to, Move, Delete options
- **Preview slider** - Adjust thumbnail size
- **Countdown timer** - Optional delay before capture

### Send Targets
- Fully managed in Settings — add any open window as a target, remove targets you no longer need
- "Add from open windows…" button enumerates all visible Windows via win32gui.EnumWindows, lets you pick one, auto-fills name & title_pattern
- Targets saved to config JSON (push_targets list) and persist across sessions
- Default targets: VSCode Claude, WhatsApp, Discord, Slack, Teams
- Auto-send dropdown (combo) always stays in sync with the target list

## Storage
- Screenshots: `~/Pictures/Screenshots` with subfolders for organization
- Config: `~/Pictures/Screenshots/screenshot_tool_config.json`
- Crash log: `~/Pictures/Screenshots/screenshot_tool_crash.log`

## Logo
Place `logo.png` in the app directory to display:
- In the sidebar (top)
- In the About dialog
- As the window/taskbar icon

## Microsoft Store Publishing

**NEW:** MSIX packaging infrastructure created for publishing to Microsoft Store!

See: `msix/TASK_CREATE_MSIX_PACKAGE.md` for Copilot implementation task  
Guide: `msix/MSIX_PUBLISHING_GUIDE.md` for complete publishing workflow

**Files to be created by Copilot:**
- `msix/AppxManifest.xml` — Package manifest
- `msix/build_msix.ps1` — Build script
- `msix/setup_msix.py` — Asset generator
- `msix/Assets/` — Store images (7 PNG files)

**Output:** `msix/OtterlyScreenshots_1.0.0.0_x64.msix` ready for Microsoft Store

## Building & Distribution

### Build standalone .exe (for sharing)
```
python build.py
```
Creates `dist/OtterlyScreenshots.exe` - a single file that runs without Python installed.

### Install on your system
```
python install.py
```
Creates:
- Desktop shortcut
- Start Menu entry
- Windows Startup shortcut (auto-start on boot)
- Enables pin-to-all-virtual-desktops in config

Uses a `.vbs` launcher (no console window flash).

### Uninstall
```
python uninstall.py
```
Removes shortcuts and startup entry (keeps app files).

## Files
| File | Purpose |
|------|---------|
| `screenshot_tool_pyqt.py` | Main application (PyQt6) |
| `screenshot_tool.py` | Legacy application (tkinter) |
| `build.py` | Build standalone .exe |
| `install.py` | Install shortcuts, startup & desktop pinning |
| `uninstall.py` | Remove shortcuts |
| `OtterlyScreenshots.vbs` | Silent launcher (no console) |
| `OtterlyScreenshots.bat` | Batch launcher |
| `logo.png` | App logo (optional) |
| `run_screenshot_tool.bat` | Quick launcher (legacy) |

## Version
Current: v2.0

## Performance (2026-10-30) — read before touching the gallery
Paul: "it is SLOW". Measured on his 912 root screenshots (offscreen harness, same code paths):
- **Every gallery refresh froze the app ~27 s** (startup ~55 s: two refreshes). Cause: the in-memory
  thumbnail LRU held 500 entries; walking 912 files in the same order every refresh means an LRU never
  hits, so every refresh decoded every full-size PNG again. Refreshes ran after every capture, every
  search keystroke, every window-resize event, folder switch, move and edit.
- Now: thumbnails come from a **disk cache** (`%LOCALAPPDATA%\OtterlyScreenshots\thumbs`, max 640x480,
  JPEG unless the image has alpha, key = path + mtime + size; outside the save folder so OCR re-index,
  storage totals and folder lists never see it; ~42 MB for 912) made by a background `ThumbnailLoader`
  QThread (QImage only; stopped on `aboutToQuit`). Tiles are kept in `_thumb_widgets` and only re-ordered
  on refresh; new tiles are created 80 per event-loop turn (`_create_missing_thumbnails`); the grid
  position is by index, so use `_gallery_order` (not grid insertion order) to re-flow. Theme, folder or
  thumbnail size change rebuilds the tiles (`_gallery_context`). Resize only re-flows (`_reflow_gallery`,
  debounced 120 ms); search is debounced 250 ms; directory listings use `os.scandir`.
- Results: refresh after a capture 27 s -> 0.04 s; search 6.5 s -> 0.03 s; startup until every thumbnail
  is shown ~4 s warm with the window usable throughout (longest stall ~0.4 s; first run ever builds the
  cache in the background, ~37 s). Folder bar 0.25 -> 0.1 s; hover preview decodes from the cache.
- Capture path: the PNG is written on a background thread (a full 3440x1440 screen took 0.9 s on the UI
  thread); gallery/folder/OCR follow in `_on_screenshot_written`. Two captures in one second get `_1`,
  `_2` names instead of overwriting. Screen grabs go BGRA -> QImage directly (`grab_to_pixmap`, no PIL);
  clipboard DIB built with one `mirrored()` instead of a Python row loop (64 -> 16 ms). Byte-identical.
- Still slow on purpose: the capture hide/settle delays (50 + 240 ms) that prevent ghosting.
- `screenshot_20260616_165903.png` (3.6 MB) is corrupt (libpng "invalid block type"); it shows no picture.
- Proof scripts (scratchpad, not in repo): harness2.py (timings), functest.py (29 checks on a scratch copy).
- Backup of the file before this change: `screenshot_tool_pyqt.py.bak_pre_speedup_2026_10_30`.

## Edit after save (2026-10-30)

Paul: *"after a save it automatically opens the edit mode. When I save the edit it automatically gets
saved to the clipboard."* Setting `edit_after_save` (default on; Settings: "Open editor after save").
- `_save_screenshot` saves and copies the capture as before, then `_open_editor_after_save` opens the
  editor on it. Closing the editor (Esc, Cancel or the window's X) keeps the capture as it was.
- Saving the edit (`_save_edited`, also used when editing from the gallery) copies the edited image to
  the clipboard at once and overwrites the file in the background: it waits for the capture's own
  write of that file (the editor opens before it finishes), writes a hidden `.<name>.edit-tmp` and
  swaps it in, so the gallery and OCR never read a half-written file. `_on_edit_written` refreshes the
  tile, the storage total and re-runs OCR.
- An auto-send (config or floating-bar target) waits for the editor: edited image if saved, the
  capture if closed.
- With "Edit before save" on, that editor runs instead and no second one opens after the save.
- `ScreenshotEditor.closeEvent` now emits `editing_cancelled` for the window's X; before, closing an
  edit-before-save editor that way left `capture_in_progress` stuck.
- Proof: functest2.py (scratchpad), 53 checks. Backup: `screenshot_tool_pyqt.py.bak_pre_edit_after_save_2026_10_30`.

## Movable objects in the editor (2026-11-03)

Paul: *"any object that I make on the chart should be movable."* The editor used to paint every stroke
straight into `overlay_pixmap`, so nothing could be picked up again. Now every annotation is an object
(a dict in `ScreenshotEditor._objects`: highlight, pen, line, arrow, rect, circle, blur, text, stamped
measure line/rect), each with its own colour, size and geometry plus a `dx`/`dy` offset.
`_paint_object` draws one; `_render_overlay` rebuilds `overlay_pixmap` from the list, oldest first.
- **Move tool** (first toolbar button, key **V**): click an object to select it (dashed teal box, on
  screen only), drag to move, **Delete**/Backspace removes it. **Ctrl+drag** moves an object from any
  tool without switching. The cursor turns into the move cross over anything that can be picked up.
- Picking (`_hit_object`): top-most first, and a drawn line beats the inside of a shape, so an arrow
  inside a rectangle is still grabbed on its shaft; the empty inside of a rect, circle, blur box or text
  grabs that object. Tolerance 6 screen pixels.
- A moved blur box redacts whatever is under it at its new place. A drag stops at the picture's edge.
- Undo stores object lists, not pictures: a move or a delete is one undo step; a click that moves
  nothing adds none. While dragging, the objects below and above are rendered once
  (`overlay_pixmap`, `_above_pixmap`) and only the dragged one is repainted (`preview_pixmap`):
  ~18-25 ms a step on a 2560x1440 picture with 30 objects.
- Drawing looks exactly as before (pixel-identical), except a stamped measurement is now smoothed, as
  its live preview always was. Text's pick-up box comes from the font's ascent/advance
  (`boundingRect` gives a broken rect under Qt's offscreen platform).
- Proof: movetest.py (scratchpad: each kind drawn = old editor, each kind moved = drawn at the new place,
  undo/delete/Ctrl+drag/picking/edges/hover), run offscreen and on the Windows platform; functest2.py
  still 53/53. Backup: `screenshot_tool_pyqt.py.bak_pre_move_objects_2026_11_03`.

## Voice note (2026-11-04)

Paul: *"a microphone as an icon on the main menu, and when I click that ... a text box that I can voice
type into ... default size 12 ... placed anywhere I want, selectable and movable ... at least 255
characters."* The 🎤 button sits on the editor toolbar right after T (an action, not a tool).
- `VoiceNoteDialog`: a 600x220 box (255+ characters show without scrolling), a character count, a
  size box starting at 12, Speak/Stop and "Add to picture" (Ctrl+Enter; Enter is a new line).
- **Speech is turned into text on this PC by offline Whisper** (faster-whisper 1.2.1, model `base`,
  int8, CPU). Paul tried Windows voice typing (Win+H) first; it did not work for him and he called it
  a cheat, so it is gone. The box starts listening when it opens (`_MicRecorder`: Qt Multimedia's
  `QAudioSource` on the default microphone, 16 kHz mono Int16, else the mic's own format resampled);
  Stop hands the recording to `_SpeechWorker` (a QThread) and the text is added at the end of the box,
  where it can be corrected; Speak more adds another piece. Add while listening writes it down first,
  then adds. Cancel drops a recording. A level bar shows the mic is heard; 5 minutes stops by itself.
  `vad_filter=True`: silence and room noise give no text. Measured: ~5 s to write down 11 s of speech;
  the model loads in ~1.5 s (warmed up in the background when the box opens, kept for the session).
- Model files: `%LOCALAPPDATA%\OtterlyScreenshots\whisper` (142 MB, downloaded 2026-11-04). Packages:
  faster-whisper and its 20-odd dependencies (84 MB) installed into `.venv`. Imported only when a
  voice note is used, so startup is untouched. Without them the box says voice typing is not
  available and typing still works.
- **The C++ runtime clash (fixed at the top of the file, `_prefer_system_cpp_runtime`)**: PyQt6 ships
  msvcp140.dll 14.26; ctranslate2 needs a newer one and crashed (access violation in WhisperModel)
  whenever Qt was loaded first. System32's msvcp140 (14.44) is now loaded before PyQt6, so both share it.
- The note becomes a `'text'` object with a `width`: wrapped at word breaks inside a box 64 average
  characters wide (`NOTE_LINE_CHARS`; narrower on small pictures), in the current colour on the
  measurement labels' dark plate (`NOTE_PLATE`, `NOTE_PAD` 8). Its `bbox` is the plate, so moving,
  picking, Delete and undo all work as for every other object. It lands in the middle of the picture,
  selected, with the Move tool on.
- Proof: speechtest.py (scratchpad: two sentences spoken by Windows text-to-speech come back word for
  word; the box's whole flow with a stand-in mic; `--mic` records 2 s of the real mic in memory),
  notetest.py, movetest.py and functest2.py all pass. Backups:
  `screenshot_tool_pyqt.py.bak_pre_voice_note_2026_11_04`, `...bak_pre_whisper_2026_11_04`.

## Several editors open at once (2026-11-04)

Paul: *"have one edit box open, and then if I record a new snippet or a new window ... a new edit box
to open with that one, leaving the old one the way it was."*
- Before: MainWindow kept ONE `self.editor`. A new capture reassigned it, the old editor lost its last
  Python reference and was destroyed, drawing and all. With "Edit before save" on, a new capture was
  blocked outright (`capture_in_progress` stayed True while that editor was open).
- Now every editor goes through `_open_editor()`, which holds it in `self._editors` until it closes
  (then `deleteLater`). There is no `self.editor` any more.
- A capture hides the open editors so they are not in the shot (`_prepare_capture_ui` records them in
  `_editors_hidden_for_capture`), and `_restore_capture_ui` shows them again where they were, on
  save and on cancel. Minimised editors are left alone.
- A new editor that would open exactly on top of another (same size, same centred spot) steps 32 px
  down-right, or sideways when a full-screen one has no room below, so the one under it shows.
- Edit before save: the capture counts as over once its editor is up, so the next capture can start.
  Saving that editor while another capture runs does not show the main window into that shot
  (`_save_screenshot(..., from_editor=True)`); closing it only says "Capture cancelled".
- Proof: functest3.py (scratchpad; functest2.py with `w.editor` replaced, plus 32 checks for two and
  three editors, same-size and full-screen captures, cancel, edit-before-save), movetest, notetest
  and speechtest all pass. Backup: `screenshot_tool_pyqt.py.bak_pre_many_editors_2026_11_04`.

## Live voice typing in any text box (2026-11-04)

Paul: *"any text box where I would normally type, I should be able to also use voice typing ...
right now I'm using voice in Claude directly using the Claude microphone, and it's instant ... showing
while I'm talking what I'm saying ... that's really what I would like."* He chose offline.
- **Ctrl+Shift+Space** anywhere starts listening, and again stops it (or ■ Stop on the strip; it also
  stops by itself after `LIVE_QUIET_STOP` 30 s with nothing said). Registered in `_register_hotkeys`
  beside the capture keys; the keyboard hook's callback emits `MainWindow.live_typing_requested`,
  a signal, so the work happens on the UI thread. Not suppressed: the app under the cursor sees the
  keys too (Word: a non-breaking space).
- **Engine**: sherpa-onnx (pip `sherpa-onnx` 2.0.1, cp314 wheel) running NVIDIA's streaming
  FastConformer, `LIVE_ASR` = the 480 ms int8 model, English only. Measured on this Ryzen 5 2600X with
  the PC 65% busy (TWS, IB Gateway, browsers): 480 ms needs ~20% of a real-time second, the 80 ms model
  51-64% (it fell behind in the app), Nemotron 0.6B 300-400% (cannot keep up), Kroko 7% but updates
  only every 1.3 s. decode releases the GIL (the UI ran at 96% speed during non-stop decoding).
- **Punctuation**: `sherpa-onnx-online-punct-en-2024-08-06` (CNN-BiLSTM, ~25 ms a phrase) puts
  capitals and marks in. `_LivePhrases` punctuates each phrase together with up to 30 earlier words
  and types only the mark the previous word gains, then the new words; a phrase's own last mark is
  held back (the model ends every lone phrase: "Can you send me the report?" + "by Tuesday?") and
  decided by the next phrase or by Stop (`ending()` asks the model with "thank you" after it, which
  reliably gives ? or .). Nothing already typed is ever changed.
- **Typing**: `_send_text` = SendInput with KEYEVENTF_UNICODE, so it works in any layout and never
  touches the clipboard. It waits while Shift/Ctrl/Alt/Win are held (they would make shortcuts),
  at most 3 s. A phrase is typed when the engine sees `LIVE_PAUSE` 0.8 s of quiet after speech.
- **Strip** (`LiveTypingStrip`): frameless, Tool, on top, `WindowDoesNotAcceptFocus` +
  `WA_ShowWithoutActivating` = WS_EX_NOACTIVATE, so it never takes the keyboard (checked on the real
  screen, Stop button included). Placed under the text cursor (`GetGUIThreadInfo`; browsers keep
  theirs private, so then the mouse). Hidden during a capture and shown again after.
- **The second listen (same day).** Paul: *"pretty good ... not perfectly happy"* — the live model
  typed "Forgotten, but naught gone". It decides each word within half a second, with no sentence
  context. Now every finished phrase is heard again, whole, by **NVIDIA Parakeet TDT 0.6B v2**
  (`LIVE_RECHECK`, int8, 482 MB, offline transducer) and ITS text is typed. Chosen by Paul's own voice
  test (`voice_test.py` in this folder: live model vs Parakeet v2 vs v3 vs Whisper, side by side,
  nothing saved) — "Parakeet v2 best". Computer voices never reproduced "naught"; on 16 TTS clips
  Parakeet fixed "for"→"four" and a dropped "I" but writes "two fifteen" as "$2.15" and "S and P" as
  "SNP". The live words still show in the strip while you talk; a phrase being checked shows in grey
  italics, then is typed. The second listen runs on its own thread (`_LiveWorker._recheck_loop`), in
  order, so the strip keeps flowing. Cost measured on this PC (busy): a 3 s phrase ~0.6 s, an 8 s one
  1.5-2.5 s, on top of the 0.8 s pause. 6 threads (90th percentile 1.2 s against 2.3 s with 4).
- Joining phrases (`_LivePhrases.take_heard`): Parakeet's words and punctuation are kept; the
  punctuation model (with the 30 words before) decides only whether a sentence ends between phrases,
  and so the first word's capital; Parakeet's own last mark is held back and used at the end (or
  between sentences when both agree a sentence ended — it hears a question in the voice). A glued
  currency sign gets its space (`_tidy_heard`). If Parakeet fails or hears nothing, the live words
  are typed (never lose words). `_ends_sentence()` exists because `"" in ".?!"` is True.
- The three models (~0.9 GB in memory) are let go `LIVE_FREE_AFTER` (15 min) after voice typing
  ends; the next use reloads them (about 10 s; the sound is kept meanwhile, nothing is lost).
- **Models** live in `%LOCALAPPDATA%\OtterlyScreenshots\sherpa` (~650 MB); a PC without them
  downloads them from the sherpa-onnx GitHub releases on first use, progress in the strip. The
  archive is unpacked to `realpath(tmp)`: under Claude's package the safety check otherwise refuses.
- Proof: livetest.py (scratchpad: two TTS sentences streamed in real time through a stand-in mic,
  100% of the words, two sentences with capitals and full stops, first sentence typed ~1.5 s after
  its last word; held keys, quiet stop, no mic, quitting mid-sentence, the download; never a real
  keystroke; the second listen, its failure, letting go and reloading), functest3.py section 10,
  movetest, notetest, speechtest all pass. Backups: `screenshot_tool_pyqt.py.bak_pre_live_typing_2026_11_04`,
  `...bak_pre_parakeet_2026_11_04`.

## Claude's desktop app keeps its own copy of %LOCALAPPDATA% (read before restarting the app)
Anything started from a Claude Code session (Bash, PowerShell, Start-Process) runs inside the Claude
MSIX package: its writes to `%LOCALAPPDATA%` land in
`C:\Users\Honey\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Local`, and it sees that copy
merged over the real folder. Paul's normal Otterly (started at login) sees only the real folder. On
2026-11-04 the Whisper and sherpa models had been downloaded into the package copy only; they were
copied to the real `C:\Users\Honey\AppData\Local\OtterlyScreenshots` with robocopy run through
`Invoke-CimMethod Win32_Process Create`, which starts a process OUTSIDE the package. Use the same to
look at the real folder (`dir`) and to restart Otterly.

## Restarting the app (read before killing it)
`OtterlyScreenshots.vbs` waits on the hidden pythonw copy, and if that copy exits with a code other
than 0 (a kill) it opens a visible `cmd /k python.exe` copy as a crash fallback. So stop the waiting
`wscript.exe` (command line ends `OtterlyScreenshots.vbs`) first, then both pythonw processes, then
start it with `Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments
@{CommandLine='wscript.exe "G:\My Drive\MyProjects\screenshot_tool\OtterlyScreenshots.vbs"'}` (not
Start-Process: that keeps it inside Claude's package, see above). Check one wscript + two pythonw
remain. First look for open editor windows ("Otterly — Edit Screenshot"): a restart loses their
unsaved drawing.

## Recent Updates
- 2026-03-08: Improved gallery responsiveness for delete/save flows in `screenshot_tool_pyqt.py`.
- Delete now removes thumbnail widgets incrementally (no full gallery rebuild for a single delete).
- OCR-index badge checks are now batched in one DB query per refresh instead of one query per image.
- Folder bar refresh is no longer forced on every gallery refresh; it is refreshed only when folder/file structure changes.
- Storage usage now uses a cached byte total and incremental updates on save/delete, avoiding repeated full directory scans.
- Gallery thumbnails now use an in-memory scaled pixmap cache with invalidation on edit/move/delete to reduce repeated decode/scale cost.
- Folder strip moved from top bar to a dedicated right sidebar with larger folder preview thumbnails.
- Folder hover now shows a tooltip-style enlarged preview (~300%) of recent images in that folder.
- Dragging a screenshot to a folder now enforces move semantics (source file removed if still present after move).
- Folder previews now render at fixed-width, double-height cards (same width, 2x height) per UX request.
- Folder hover preview now uses the same fixed-width, double-height style at larger scale.
- Move now uses robust rename/copy-delete fallback with unique destination naming to prevent accidental copies/overwrites.
- Root/main gallery view now lists only root-level PNG files (not recursive subfolder files), so moved images disappear from root immediately.
- Settings now include folder thumbnail size control (`folder_thumbnail_scale`) in addition to main gallery thumbnail size.
- Thumbnail-size changes now refresh from cached visible image list (faster apply after Save in Settings).
- Main window is now resizable via bottom-right grip while keeping frameless style.
- Folder sidebar is independently resizable from the gallery via a splitter handle.
- Scrollbars updated with a more dimensional/3D-styled handle and hover effect.
- Frameless main window now supports edge/corner drag-resize via native `startSystemResize` hit-testing.
- Main gallery and folder sidebar scroll areas now apply explicit high-contrast scrollbar styling directly.
- Main window uses native OS window frame resizing for standard edge hover cursors and drag behavior (stability-first fallback from custom frameless resize hooks).
- Startup hang/crash root cause isolated to `MainWindow.nativeEvent` delegating to `super().nativeEvent(...)` during first `show()` on Python 3.14/PyQt6; fixed by returning `(False, 0)` when not actively handling custom hit-test messages, which restores reliable startup and event-loop entry.
- Restored custom frameless window look with native Windows `WM_NCHITTEST` edge/corner resize handling for standard resize cursors and drag behavior.
- Main vertical scrollbars now auto-hide and reveal on hover (gallery + folder sidebar).
- Removed `pyautogui` dependency for paste-send and now use `keyboard` hotkey emit, reducing DPI-awareness conflicts at startup.
- Startup immediate-exit diagnosis: active `.venv` was missing `PyQt6` (`ModuleNotFoundError`); app now bootstraps `PyQt6` install at startup (matching other dependency auto-install behavior).
- PyQt6 bootstrap is now strict: startup checks pip install exit code, shows a native Windows error dialog on failure, and exits cleanly instead of crashing with an import traceback.
- Launchers (`OtterlyScreenshots.vbs` and `OtterlyScreenshots.bat`) now prefer workspace `.venv\Scripts\pythonw.exe` before falling back to `C:\Python314\pythonw.exe`, fixing silent startup failures caused by mismatched system Python.
- `install.py` now generates the same venv-first launcher logic, preventing future reinstalls from reintroducing system-Python startup failures.
- Config load/save is now BOM-safe (`utf-8-sig` on load, `utf-8` on save), fixing `Failed to load config: line 1 column 1` startup issues.
- Startup now force-brings the main window to front (`showNormal`/`raise_`/`activateWindow` timers) to avoid silent background-only launches.
- Floating bar restore now validates saved position against current screen bounds and auto-recovers to a visible top-center location if off-screen.
- Hotkey registration now runs in a background thread (`_register_hotkeys_nonblocking`) so startup cannot hang before the main window is shown.
- Main window now explicitly sets `setWindowTitle(APP_NAME)` for reliable taskbar/window identification.
- `OtterlyScreenshots.vbs` now detects fast hidden startup exits and auto-falls back to visible `python.exe` launch (`cmd /k`) so failures are no longer silent when clicking the desktop link.
- VBS visible fallback command now wraps full interpreter/script payload with nested quotes (`cmd /k ""..." "...""`) so paths under `G:\My Drive\...` are parsed correctly.
- `install.py` launcher template updated to generate the same robust quoted fallback behavior for future installs.
- Main window uses native OS window frame resizing for standard edge hover cursors and drag behavior (stability-first fallback from custom frameless resize hooks).
- 2026-03-10: Sidebar cleanup in `screenshot_tool_pyqt.py` removes bottom clutter from the right menu (Storage/Screenshots/About hidden) and keeps uniform button spacing.
- Thumbnail right-click menu now has two explicit open actions: `Open Image` and `Open OCR Text`.
- Added `OcrIndex.get_text(filepath)` and `_open_ocr_text(filepath)`; OCR text opens in the system text editor from a temp `.txt` file, with a friendly message when OCR text is not available yet.
- Right sidebar folder cards now render a folder-like preview shell; latest image preview appears inside the folder body for a clearer "actual folder" visual.
- Fixed runtime crash in folder preview paint path: `QPainterPath.addRoundedRect(...)` now uses `QRectF` (PyQt6 overload requirement) instead of `QRect`.
- Folder card artwork was restyled to a more classic folder silhouette (back tab + front pocket with angled edge) to avoid phone-like appearance.
- Folder icon preview now expands to fill the full folder-card preview area (instead of rendering as a small centered icon).
- Folder preview now renders as part of the folder surface itself (no separate inner thumbnail frame), and card proportions were adjusted away from tall phone-like aspect.
- Folder list items now remove outer card framing entirely (transparent container) so each row is just the folder graphic; folder names are rendered directly on the folder tab.
- Root sidebar folder label was renamed from `All` to `Main` for clearer naming in the folder list UI.
- Removed the top `Folders` header label from the sidebar so folder rows start immediately at the top.
- Folder sidebar cards are now ~2x taller and render a 3-miniature screenshot strip from folder contents (newest image on the left).
- Folder miniature strip now uses an overlapping "stacked-paper" layout (still newest on the left) for a stronger folder-preview look.
- Title-bar search input styling now forces high-contrast text/placeholder/border colors for better readability across themes.
- Main gallery now shows a current-folder badge (`Main` or selected folder name) above thumbnails, styled to match the folder-tab label look.
- Capture flow now hard-hides both main window and floating bar before region/window/screen capture and restores UI afterward, preventing Otterly windows from appearing during selection.
- Capture pre-hide now also forces Otterly windows to temporary 0-opacity before hide and uses a slightly longer pre-capture settle delay to avoid transparent DWM ghosting in region overlays.
- Reworked capture pre-hide to avoid opacity transitions (which could leave translucent ghosts): now uses strict hide + `DwmFlush()` + longer settle delay before region/fullscreen capture.
- Main content splitters now use thin 3D divider styling; left sidebar divider is fixed/non-resizable, while the gallery/folder divider remains resizable.
- Gallery/folder splitter resize now uses non-opaque dragging for smoother interaction on heavy thumbnail scenes.
- Gallery and folder scroll areas now offset viewport margins so hover scrollbars visually overlap divider edges instead of sitting beside them.
- Divider and scrollbar visual tuning in `screenshot_tool_pyqt.py`:
  - Left divider now uses a custom `ThreeDLine` widget with a 3D effect matching the background color (not resizable, visually distinct).
  - Gallery scrollbar is offset 10px to the right for improved visual separation from the divider.
  - Default splitter handle styling removed for left divider; right divider remains resizable and styled as before.
