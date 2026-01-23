# Screenshot Tool

## Project Type
**Python 3 + tkinter** - single-file Python application

## How to Run
Double-click `run_screenshot_tool.bat` or run:
```
python screenshot_tool.py
```

## Main File
`screenshot_tool.py` - single-file Python application (~3300 lines)

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
- **Drag-and-drop** - Drag screenshots between folders
- **Storage management** - View folder sizes and delete old screenshots

### Editing
- **Highlight tool** - Add colored highlights (yellow, green, blue, red) before saving
- **Edit existing** - Open saved screenshots in editor to add highlights

### Workflow
- **Silent capture mode** - Capture without showing main window
- **Auto-send** - Automatically send to configured apps (VSCode Claude, etc.)
- **Import/Paste** - Import from file or paste from clipboard
- **Copy to clipboard** - All captures automatically copied

### Gallery
- **Hover menu** - Floating menu with Open, Edit, Copy, Send, Move, Delete buttons
- **Preview slider** - Adjust thumbnail size
- **Countdown timer** - Optional delay before capture

## Storage
Saves to `~/Pictures/Screenshots` with subfolders for organization

## Version
Current: v1.15
