# Otterly Screenshots

## Project Type
**Python 3 + tkinter** - single-file Python application

## How to Run
Double-click `run_screenshot_tool.bat` or run:
```
python screenshot_tool.py
```

## Main File
`screenshot_tool.py` - single-file Python application (~3500 lines)

## Key Dependencies
- PIL/Pillow - image handling and editing
- keyboard - global hotkeys
- mss - screen capture
- pyautogui/pygetwindow - window management
- win32clipboard - clipboard operations
- win32gui - window selection

## Features

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
- **Import/Paste** - Import from file or paste from clipboard
- **Copy to clipboard** - All captures automatically copied
- **Rapid capture** - Take multiple screenshots in succession without interruption

### Gallery
- **Context menu** - Right-click thumbnails for Open, Edit, Copy, Send, Move, Delete options
- **Preview slider** - Adjust thumbnail size
- **Countdown timer** - Optional delay before capture

## Storage
Saves to `~/Pictures/Screenshots` with subfolders for organization

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
- Auto-start with Windows (optional)

### Uninstall
```
python uninstall.py
```
Removes shortcuts and startup entry (keeps app files).

## Files
| File | Purpose |
|------|---------|
| `screenshot_tool.py` | Main application |
| `build.py` | Build standalone .exe |
| `install.py` | Install shortcuts & auto-start |
| `uninstall.py` | Remove shortcuts |
| `logo.png` | App logo (optional) |
| `run_screenshot_tool.bat` | Quick launcher |

## Version
Current: v1.20
