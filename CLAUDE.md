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
