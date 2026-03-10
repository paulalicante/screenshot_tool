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
