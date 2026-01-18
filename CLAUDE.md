# Screenshot Tool

## Project Type
**Python 3 + tkinter** (NOT Flutter - ignore the Flutter files in this project)

## How to Run
Double-click `run_screenshot_tool.bat` or run:
```
python screenshot_tool.py
```

## Main File
`screenshot_tool.py` - single-file Python application

## Key Dependencies
- PIL/Pillow - image handling
- keyboard - global hotkeys
- mss - screen capture
- pyautogui/pygetwindow - window management
- win32clipboard - clipboard operations

## Features
- Global hotkeys: Ctrl+Shift+S (full screen), Ctrl+Shift+R (region)
- Screenshot gallery with floating hover menu (Open, Copy, Del buttons)
- Auto-paste to VSCode Claude option
- Saves to ~/Pictures/Screenshots

## Notes
- Hover menu UI is functional but basic - may revisit for sleeker design later
