"""
Screenshot Tool - A simple Windows screenshot utility
Features:
- Global hotkey (Ctrl+Shift+S) to capture full screen
- Global hotkey (Ctrl+Shift+R) to capture a region
- Auto-save with timestamps
- Auto-paste to VSCode Claude (optional)
- Thumbnail gallery to view recent screenshots
- Click thumbnails to open full images
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import sys
from datetime import datetime
from pathlib import Path
import subprocess
import time

# Check and install required packages
def install_package(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package, "--quiet"])

try:
    from PIL import Image, ImageTk, ImageGrab
except ImportError:
    print("Installing Pillow...")
    install_package("Pillow")
    from PIL import Image, ImageTk, ImageGrab

try:
    import keyboard
except ImportError:
    print("Installing keyboard...")
    install_package("keyboard")
    import keyboard

try:
    import mss
except ImportError:
    print("Installing mss...")
    install_package("mss")
    import mss

try:
    import pyautogui
    import pygetwindow as gw
except ImportError:
    print("Installing pyautogui and pygetwindow...")
    install_package("pyautogui")
    install_package("pygetwindow")
    import pyautogui
    import pygetwindow as gw


class DelayCountdown:
    """Shows a countdown timer before capturing"""

    def __init__(self, seconds, callback):
        self.seconds_left = seconds
        self.callback = callback

        # Create small floating window
        self.window = tk.Toplevel()
        self.window.title("Countdown")
        self.window.attributes('-topmost', True)
        self.window.overrideredirect(True)  # No window decorations

        # Position in top-right corner of screen
        screen_w = self.window.winfo_screenwidth()
        self.window.geometry(f"150x80+{screen_w - 170}+20")

        # Style the window
        self.window.configure(bg='#333333')

        # Countdown label
        self.label = tk.Label(
            self.window,
            text=str(self.seconds_left),
            font=("Arial", 36, "bold"),
            fg="white",
            bg='#333333'
        )
        self.label.pack(expand=True)

        # Info label
        self.info_label = tk.Label(
            self.window,
            text="Set up your screen...",
            font=("Arial", 9),
            fg="#aaaaaa",
            bg='#333333'
        )
        self.info_label.pack()

        # Cancel button (small)
        cancel_btn = tk.Button(
            self.window,
            text="Cancel",
            command=self.cancel,
            font=("Arial", 8),
            bg='#555555',
            fg='white',
            relief=tk.FLAT,
            cursor='hand2'
        )
        cancel_btn.pack(pady=5)

        # Bind Escape to cancel
        self.window.bind('<Escape>', lambda e: self.cancel())

        # Start countdown
        self.tick()

    def tick(self):
        if self.seconds_left <= 0:
            self.window.destroy()
            self.callback(True)  # Capture now
            return

        self.label.config(text=str(self.seconds_left))

        # Change color as countdown progresses
        if self.seconds_left <= 2:
            self.label.config(fg='#ff5555')  # Red for last 2 seconds
        elif self.seconds_left <= 3:
            self.label.config(fg='#ffaa00')  # Orange

        self.seconds_left -= 1
        self.window.after(1000, self.tick)

    def cancel(self):
        self.window.destroy()
        self.callback(False)  # Cancelled


class WindowSelector:
    """Overlay for selecting a window to capture"""

    def __init__(self, callback):
        self.callback = callback
        self.handled = False  # Guard against multiple clicks

        # Create fullscreen semi-transparent overlay
        self.overlay = tk.Toplevel()
        self.overlay.attributes('-fullscreen', True)
        self.overlay.attributes('-alpha', 0.15)  # Semi-transparent - enough to capture clicks
        self.overlay.attributes('-topmost', True)
        self.overlay.configure(bg='black')

        # Instructions window (separate small window)
        self.info_window = tk.Toplevel()
        self.info_window.attributes('-topmost', True)
        self.info_window.overrideredirect(True)
        self.info_window.configure(bg='#333333')

        # Position info window at top center
        screen_w = self.info_window.winfo_screenwidth()
        self.info_window.geometry(f"350x50+{(screen_w - 350) // 2}+20")

        tk.Label(
            self.info_window,
            text="Click on any window to capture it\nPress ESC to cancel",
            font=("Arial", 11),
            fg="white",
            bg='#333333'
        ).pack(expand=True)

        # Bind click on overlay
        self.overlay.bind('<Button-1>', self.on_click)
        self.overlay.bind('<Escape>', self.on_cancel)
        self.info_window.bind('<Escape>', self.on_cancel)

        # Focus the overlay to receive clicks
        self.overlay.focus_force()
        self.overlay.lift()

    def on_click(self, event):
        """Get the window at click position"""
        # Guard against multiple click events
        if self.handled:
            return
        self.handled = True

        import win32gui
        import win32con

        # Get screen coordinates
        x, y = event.x_root, event.y_root

        # Close our overlays
        self.overlay.destroy()
        self.info_window.destroy()

        # Small delay to ensure overlay is gone
        time.sleep(0.1)

        # Get the window at this position
        hwnd = win32gui.WindowFromPoint((x, y))

        if hwnd:
            # Get the top-level parent window
            root_hwnd = win32gui.GetAncestor(hwnd, win32con.GA_ROOT)
            if root_hwnd:
                hwnd = root_hwnd

            self.callback(hwnd)
        else:
            self.callback(None)

    def on_cancel(self, event):
        if self.handled:
            return
        self.handled = True
        self.overlay.destroy()
        self.info_window.destroy()
        self.callback(None)


class RegionSelector:
    """Fullscreen overlay for selecting a screen region"""

    def __init__(self, callback):
        self.callback = callback
        self.start_x = None
        self.start_y = None
        self.rect = None

        # Create fullscreen window
        self.overlay = tk.Toplevel()
        self.overlay.attributes('-fullscreen', True)
        self.overlay.attributes('-alpha', 0.3)
        self.overlay.attributes('-topmost', True)
        self.overlay.configure(bg='black')

        # Create canvas for drawing selection rectangle
        self.canvas = tk.Canvas(
            self.overlay,
            highlightthickness=0,
            bg='black',
            cursor='crosshair'
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Instructions label
        self.label = tk.Label(
            self.overlay,
            text="Click and drag to select region. Press ESC to cancel.",
            font=("Arial", 14),
            fg="white",
            bg="black"
        )
        self.label.place(relx=0.5, y=30, anchor='center')

        # Bind events
        self.canvas.bind('<Button-1>', self.on_press)
        self.canvas.bind('<B1-Motion>', self.on_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_release)
        self.overlay.bind('<Escape>', self.on_cancel)

        # Focus the overlay
        self.overlay.focus_force()

    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        # Create rectangle
        self.rect = self.canvas.create_rectangle(
            self.start_x, self.start_y,
            self.start_x, self.start_y,
            outline='red',
            width=2,
            fill='white',
            stipple='gray50'
        )

    def on_drag(self, event):
        if self.rect:
            self.canvas.coords(
                self.rect,
                self.start_x, self.start_y,
                event.x, event.y
            )

    def on_release(self, event):
        if self.start_x is None:
            return

        # Get the selected region coordinates
        x1 = min(self.start_x, event.x)
        y1 = min(self.start_y, event.y)
        x2 = max(self.start_x, event.x)
        y2 = max(self.start_y, event.y)

        # Close overlay
        self.overlay.destroy()

        # Check if region is valid (at least 10x10 pixels)
        if x2 - x1 > 10 and y2 - y1 > 10:
            # Small delay to let overlay fully close
            self.callback((x1, y1, x2, y2))
        else:
            self.callback(None)

    def on_cancel(self, event):
        self.overlay.destroy()
        self.callback(None)


class ScreenshotEditor:
    """Editor window for highlighting screenshots before saving"""

    # Highlight colors with semi-transparency (RGBA)
    COLORS = {
        'yellow': (255, 255, 0, 100),
        'green': (0, 255, 0, 100),
        'blue': (0, 150, 255, 100),
        'red': (255, 0, 0, 100),
    }

    def __init__(self, image, callback):
        """
        image: PIL Image to edit
        callback: function(edited_image or None) - None means cancelled
        """
        self.original_image = image.copy()
        self.image = image.copy().convert('RGBA')
        self.callback = callback
        self.current_color = 'yellow'
        self.drawing = False
        self.last_x = None
        self.last_y = None
        self.brush_size = 20
        self.horizontal_lock = False
        self.lock_y = None  # Y coordinate to lock to when horizontal lock is on
        self.draw_mode = 'highlight'  # 'highlight' or 'circle'
        self.center_x = None  # For circle mode
        self.center_y = None

        # Create highlight layer (transparent)
        self.highlight_layer = Image.new('RGBA', self.image.size, (0, 0, 0, 0))
        # Preview layer for shapes being drawn (circles)
        self.preview_layer = Image.new('RGBA', self.image.size, (0, 0, 0, 0))

        # Create editor window
        self.window = tk.Toplevel()
        self.window.title("Edit Screenshot - Highlighter")
        self.window.attributes('-topmost', True)

        # Calculate window size (fit to screen with some margin)
        screen_w = self.window.winfo_screenwidth() - 100
        screen_h = self.window.winfo_screenheight() - 150
        img_w, img_h = self.image.size

        # Scale if image is too large
        self.scale = min(1.0, screen_w / img_w, screen_h / img_h)
        self.display_w = int(img_w * self.scale)
        self.display_h = int(img_h * self.scale)

        # Toolbar frame
        toolbar = tk.Frame(self.window, bg='#f0f0f0', pady=5)
        toolbar.pack(fill=tk.X)

        # Color buttons
        tk.Label(toolbar, text="Highlight:", bg='#f0f0f0').pack(side=tk.LEFT, padx=(10, 5))

        self.color_buttons = {}
        for color_name, rgba in self.COLORS.items():
            hex_color = '#{:02x}{:02x}{:02x}'.format(rgba[0], rgba[1], rgba[2])
            btn = tk.Button(
                toolbar, text="", width=3, bg=hex_color,
                relief=tk.RAISED, bd=2,
                command=lambda c=color_name: self.select_color(c)
            )
            btn.pack(side=tk.LEFT, padx=2)
            self.color_buttons[color_name] = btn

        # Highlight the default selected color
        self.color_buttons[self.current_color].config(relief=tk.SUNKEN, bd=3)

        # Mode buttons (Highlight vs Circle)
        tk.Label(toolbar, text="  Mode:", bg='#f0f0f0').pack(side=tk.LEFT, padx=(10, 5))
        self.mode_buttons = {}

        btn_highlight = tk.Button(toolbar, text="Highlight", width=7,
                                  relief=tk.SUNKEN, bd=2,
                                  command=lambda: self.select_mode('highlight'))
        btn_highlight.pack(side=tk.LEFT, padx=2)
        self.mode_buttons['highlight'] = btn_highlight

        btn_circle = tk.Button(toolbar, text="Circle", width=7,
                               relief=tk.RAISED, bd=2,
                               command=lambda: self.select_mode('circle'))
        btn_circle.pack(side=tk.LEFT, padx=2)
        self.mode_buttons['circle'] = btn_circle

        btn_text = tk.Button(toolbar, text="Text", width=7,
                             relief=tk.RAISED, bd=2,
                             command=lambda: self.select_mode('text'))
        btn_text.pack(side=tk.LEFT, padx=2)
        self.mode_buttons['text'] = btn_text

        # Brush size
        tk.Label(toolbar, text="  Size:", bg='#f0f0f0').pack(side=tk.LEFT, padx=(10, 5))
        self.size_var = tk.IntVar(value=self.brush_size)
        size_scale = tk.Scale(toolbar, from_=5, to=50, orient=tk.HORIZONTAL,
                              variable=self.size_var, length=100, bg='#f0f0f0',
                              command=lambda v: setattr(self, 'brush_size', int(v)))
        size_scale.pack(side=tk.LEFT)

        # Horizontal lock checkbox
        self.lock_var = tk.BooleanVar(value=False)
        lock_check = tk.Checkbutton(toolbar, text="Straight Line", variable=self.lock_var,
                                    bg='#f0f0f0', activebackground='#f0f0f0',
                                    command=self.toggle_lock)
        lock_check.pack(side=tk.LEFT, padx=(15, 5))

        # Spacer
        tk.Frame(toolbar, bg='#f0f0f0').pack(side=tk.LEFT, expand=True, fill=tk.X)

        # Save and Cancel buttons
        btn_cancel = tk.Button(toolbar, text="Cancel", bg='#f44336', fg='white',
                               command=self.cancel, padx=15)
        btn_cancel.pack(side=tk.RIGHT, padx=5)

        btn_save = tk.Button(toolbar, text="Save", bg='#4CAF50', fg='white',
                             command=self.save, padx=15)
        btn_save.pack(side=tk.RIGHT, padx=5)

        # Canvas for image
        self.canvas = tk.Canvas(self.window, width=self.display_w, height=self.display_h,
                                cursor='crosshair', bg='gray')
        self.canvas.pack(padx=10, pady=10)

        # Display the image
        self.update_display()

        # Bind mouse events
        self.canvas.bind('<Button-1>', self.on_press)
        self.canvas.bind('<B1-Motion>', self.on_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_release)
        self.window.bind('<Escape>', lambda e: self.cancel())

        # Center window
        self.window.update_idletasks()
        win_w = self.window.winfo_width()
        win_h = self.window.winfo_height()
        x = (self.window.winfo_screenwidth() - win_w) // 2
        y = (self.window.winfo_screenheight() - win_h) // 2
        self.window.geometry(f'+{x}+{y}')

        # Focus
        self.window.focus_force()

        # Handle window close
        self.window.protocol("WM_DELETE_WINDOW", self.cancel)

    def select_color(self, color_name):
        """Select a highlight color"""
        # Reset all buttons
        for name, btn in self.color_buttons.items():
            btn.config(relief=tk.RAISED, bd=2)
        # Highlight selected
        self.color_buttons[color_name].config(relief=tk.SUNKEN, bd=3)
        self.current_color = color_name

    def select_mode(self, mode):
        """Select drawing mode (highlight or circle)"""
        for name, btn in self.mode_buttons.items():
            btn.config(relief=tk.RAISED, bd=2)
        self.mode_buttons[mode].config(relief=tk.SUNKEN, bd=2)
        self.draw_mode = mode

    def toggle_lock(self):
        """Toggle horizontal lock mode"""
        self.horizontal_lock = self.lock_var.get()

    def update_display(self):
        """Update the canvas with current image + highlights"""
        # Composite highlight layer onto image
        display_img = Image.alpha_composite(self.image, self.highlight_layer)
        # Add preview layer (for shapes being drawn)
        display_img = Image.alpha_composite(display_img, self.preview_layer)

        # Convert to RGB for display
        display_img = display_img.convert('RGB')

        # Scale for display
        if self.scale < 1.0:
            display_img = display_img.resize((self.display_w, self.display_h), Image.Resampling.LANCZOS)

        # Convert to PhotoImage
        self.photo = ImageTk.PhotoImage(display_img)
        self.canvas.delete('all')
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)

    def canvas_to_image_coords(self, x, y):
        """Convert canvas coordinates to image coordinates"""
        return int(x / self.scale), int(y / self.scale)

    def on_press(self, event):
        x, y = self.canvas_to_image_coords(event.x, event.y)

        if self.draw_mode == 'text':
            # Text mode - show dialog to enter text
            self.show_text_dialog(x, y)
            return

        self.drawing = True

        if self.draw_mode == 'circle':
            # Store center point for circle
            self.center_x, self.center_y = x, y
        else:
            # Highlight mode
            self.last_x, self.last_y = x, y
            # Lock the Y position if horizontal lock is enabled
            if self.horizontal_lock:
                self.lock_y = self.last_y
            self.draw_highlight(self.last_x, self.last_y)

    def on_drag(self, event):
        if self.drawing:
            x, y = self.canvas_to_image_coords(event.x, event.y)

            if self.draw_mode == 'circle':
                # Draw circle preview from center to current point
                self.draw_circle_preview(x, y)
            else:
                # Highlight mode
                # Use locked Y if horizontal lock is enabled
                if self.horizontal_lock and self.lock_y is not None:
                    y = self.lock_y
                self.draw_line(self.last_x, self.last_y, x, y)
                self.last_x, self.last_y = x, y

    def on_release(self, event):
        if self.drawing and self.draw_mode == 'circle':
            # Commit the circle to the highlight layer
            x, y = self.canvas_to_image_coords(event.x, event.y)
            self.commit_circle(x, y)

        self.drawing = False
        self.last_x = None
        self.last_y = None
        self.lock_y = None
        self.center_x = None
        self.center_y = None

    def draw_highlight(self, x, y):
        """Draw a highlight circle at position"""
        from PIL import ImageDraw
        draw = ImageDraw.Draw(self.highlight_layer)
        color = self.COLORS[self.current_color]
        r = self.brush_size // 2
        draw.ellipse([x - r, y - r, x + r, y + r], fill=color)
        self.update_display()

    def draw_line(self, x1, y1, x2, y2):
        """Draw a highlight line between two points"""
        from PIL import ImageDraw
        draw = ImageDraw.Draw(self.highlight_layer)
        color = self.COLORS[self.current_color]
        draw.line([x1, y1, x2, y2], fill=color, width=self.brush_size)
        # Draw circles at endpoints for smooth lines
        r = self.brush_size // 2
        draw.ellipse([x2 - r, y2 - r, x2 + r, y2 + r], fill=color)
        self.update_display()

    def draw_circle_preview(self, x, y):
        """Draw a preview of the circle/oval being created"""
        from PIL import ImageDraw
        # Clear preview layer
        self.preview_layer = Image.new('RGBA', self.image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(self.preview_layer)
        color = self.COLORS[self.current_color]

        # Calculate radii based on distance from center
        rx = abs(x - self.center_x)
        ry = abs(y - self.center_y)

        if rx > 2 or ry > 2:  # Only draw if dragged a bit
            # Draw ellipse outline (thicker line for visibility)
            bbox = [self.center_x - rx, self.center_y - ry,
                    self.center_x + rx, self.center_y + ry]
            # Draw with stroke width based on brush size
            for offset in range(self.brush_size // 2):
                draw.ellipse([bbox[0] - offset, bbox[1] - offset,
                             bbox[2] + offset, bbox[3] + offset],
                            outline=color)

        self.update_display()

    def commit_circle(self, x, y):
        """Commit the circle to the highlight layer"""
        from PIL import ImageDraw
        # Clear preview
        self.preview_layer = Image.new('RGBA', self.image.size, (0, 0, 0, 0))

        # Draw final circle on highlight layer
        draw = ImageDraw.Draw(self.highlight_layer)
        color = self.COLORS[self.current_color]

        rx = abs(x - self.center_x)
        ry = abs(y - self.center_y)

        if rx > 2 or ry > 2:
            bbox = [self.center_x - rx, self.center_y - ry,
                    self.center_x + rx, self.center_y + ry]
            # Draw with stroke width
            for offset in range(self.brush_size // 2):
                draw.ellipse([bbox[0] - offset, bbox[1] - offset,
                             bbox[2] + offset, bbox[3] + offset],
                            outline=color)

        self.update_display()

    def show_text_dialog(self, x, y):
        """Show a dialog to enter text, then draw it at position"""
        from tkinter import simpledialog

        # Ask for text input
        text = simpledialog.askstring(
            "Add Text",
            "Enter text to add:",
            parent=self.window
        )

        if text:
            self.draw_text(x, y, text)

    def draw_text(self, x, y, text):
        """Draw text at the specified position"""
        from PIL import ImageDraw, ImageFont

        draw = ImageDraw.Draw(self.highlight_layer)
        color = self.COLORS[self.current_color]

        # Use brush_size to determine font size (scaled up for readability)
        font_size = self.brush_size * 2

        # Try to load a nice font, fall back to default
        try:
            # Try common Windows fonts
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            try:
                font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", font_size)
            except:
                # Fall back to default font
                font = ImageFont.load_default()

        # Draw text with a slight outline for better visibility
        # Draw outline by drawing text offset in each direction
        outline_color = (0, 0, 0, 150)  # Semi-transparent black
        for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1), (-1, 0), (1, 0), (0, -1), (0, 1)]:
            draw.text((x + dx, y + dy), text, font=font, fill=outline_color)

        # Draw main text
        draw.text((x, y), text, font=font, fill=color)

        self.update_display()

    def save(self):
        """Save the edited image"""
        # Composite and convert to RGB
        final_image = Image.alpha_composite(self.image, self.highlight_layer)
        final_image = final_image.convert('RGB')
        self.window.destroy()
        self.callback(final_image)

    def cancel(self):
        """Cancel editing"""
        self.window.destroy()
        self.callback(None)


class ScreenshotTool:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Screenshot Tool v1.04")
        self.root.geometry("600x550")
        self.root.minsize(400, 350)

        # Set up save directory
        self.save_dir = Path.home() / "Pictures" / "Screenshots"
        self.save_dir.mkdir(parents=True, exist_ok=True)

        # Hotkey configuration
        self.hotkey_full = "ctrl+shift+s"
        self.hotkey_region = "ctrl+shift+r"
        self.hotkey_window = "ctrl+shift+w"
        self.hotkeys_registered = False
        self._capture_in_progress = False  # Prevent multiple simultaneous captures

        # Screenshot counter for this session
        self.screenshot_count = 0

        # Auto-paste to Claude setting
        self.auto_paste_claude = tk.BooleanVar(value=False)

        # Edit before save setting (default: True - show editor)
        self.edit_before_save = tk.BooleanVar(value=True)

        # Build the UI
        self.setup_ui()

        # Register global hotkeys
        self.register_hotkeys()

        # Load existing screenshots
        self.refresh_gallery()

        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def setup_ui(self):
        # Main frame with padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Initialize settings variables (needed for settings dialog)
        self.capture_mode_var = tk.StringVar(value="Region")
        self.delay_var = tk.StringVar(value="0")
        self.thumbnail_scale = tk.IntVar(value=5)  # 1-10, 5 = current size (120x90)
        self.disk_limit_mb = tk.IntVar(value=500)  # Max disk space in MB
        self.archive_days = tk.IntVar(value=30)  # Days before suggesting cleanup

        # Top bar - Hotkey reminder and settings button
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.X, pady=(0, 10))

        # Hotkey buttons - show shortcuts and act as clickable triggers
        hotkey_frame = ttk.Frame(top_frame)
        hotkey_frame.pack(side=tk.LEFT)

        btn_style = {"width": 18}
        ttk.Button(
            hotkey_frame, text="Ctrl+Shift+R: Region",
            command=self.start_region_capture, **btn_style
        ).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(
            hotkey_frame, text="Ctrl+Shift+S: Screen",
            command=self.capture_fullscreen, **btn_style
        ).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(
            hotkey_frame, text="Ctrl+Shift+W: Window",
            command=self.start_window_capture, **btn_style
        ).pack(side=tk.LEFT)

        # Settings button (gear icon using unicode)
        settings_btn = ttk.Button(
            top_frame,
            text="\u2699 Settings",
            command=self.show_settings,
            width=10
        )
        settings_btn.pack(side=tk.RIGHT)

        # Disk usage indicator (to the left of Settings)
        self.disk_usage_var = tk.StringVar(value="")
        self.disk_label = tk.Label(top_frame, textvariable=self.disk_usage_var, font=("", 8), fg="gray")
        self.disk_label.pack(side=tk.RIGHT, padx=(0, 10))

        # Status label
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(main_frame, textvariable=self.status_var, foreground="gray")
        status_label.pack(fill=tk.X, pady=(0, 5))

        # Gallery section
        gallery_label = ttk.Label(main_frame, text="Recent Screenshots:", font=("", 10, "bold"))
        gallery_label.pack(fill=tk.X, pady=(10, 5))

        # Canvas with scrollbar for gallery
        gallery_container = ttk.Frame(main_frame)
        gallery_container.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(gallery_container, bg="white")
        scrollbar = ttk.Scrollbar(gallery_container, orient=tk.VERTICAL, command=self.canvas.yview)

        self.gallery_frame = ttk.Frame(self.canvas)

        self.canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas_window = self.canvas.create_window((0, 0), window=self.gallery_frame, anchor=tk.NW)

        # Configure canvas scrolling
        self.gallery_frame.bind("<Configure>", self.on_frame_configure)
        self.canvas.bind("<Configure>", self.on_canvas_configure)

        # Mouse wheel scrolling
        self.canvas.bind_all("<MouseWheel>", self.on_mousewheel)

        # Counter display
        self.counter_var = tk.StringVar(value="Screenshots this session: 0")
        counter_label = ttk.Label(main_frame, textvariable=self.counter_var)
        counter_label.pack(fill=tk.X, pady=(10, 0))

    def on_frame_configure(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def register_hotkeys(self):
        try:
            keyboard.add_hotkey(self.hotkey_full, self.capture_fullscreen_threadsafe)
            keyboard.add_hotkey(self.hotkey_region, self.start_region_capture_threadsafe)
            keyboard.add_hotkey(self.hotkey_window, self.start_window_capture_threadsafe)
            self.hotkeys_registered = True
            print(f"Global hotkeys registered:")
            print(f"  {self.hotkey_region} - Region capture")
            print(f"  {self.hotkey_full} - Full screen capture")
            print(f"  {self.hotkey_window} - Window capture")
        except Exception as e:
            print(f"Failed to register hotkeys: {e}")
            self.status_var.set(f"Warning: Could not register global hotkeys - {e}")

    def unregister_hotkeys(self):
        if self.hotkeys_registered:
            try:
                keyboard.remove_hotkey(self.hotkey_full)
                keyboard.remove_hotkey(self.hotkey_region)
                keyboard.remove_hotkey(self.hotkey_window)
            except:
                pass

    def start_window_capture_threadsafe(self):
        # Prevent multiple hotkey triggers
        if self._capture_in_progress:
            return
        self._capture_in_progress = True
        # Delay to allow hotkey keys to be released before showing selector
        self.root.after(150, self.start_window_capture)

    def capture_fullscreen_threadsafe(self):
        if self._capture_in_progress:
            return
        self._capture_in_progress = True
        self.root.after(0, self.capture_fullscreen)

    def start_region_capture_threadsafe(self):
        if self._capture_in_progress:
            return
        self._capture_in_progress = True
        self.root.after(0, self.start_region_capture)

    def do_capture(self):
        """Dispatch capture based on selected mode"""
        mode = self.capture_mode_var.get()
        if mode == "Region":
            self.start_region_capture()
        elif mode == "Window":
            self.start_window_capture()
        elif mode == "Full Screen":
            self.capture_fullscreen()

    def start_window_capture(self):
        """Start the window selection process"""
        delay = int(self.delay_var.get())

        if delay > 0:
            self.status_var.set(f"Countdown: {delay} seconds - set up your screen!")
            self.root.iconify()
            self.root.after(200, lambda: DelayCountdown(delay, self._on_window_delay_complete))
        else:
            self.status_var.set("Click on a window to capture...")
            self.root.update()
            self.root.iconify()
            self.root.after(200, self._show_window_selector)

    def _on_window_delay_complete(self, proceed):
        """Called when window delay countdown finishes"""
        if proceed:
            self._show_window_selector()
        else:
            self.root.deiconify()
            self.status_var.set("Capture cancelled")

    def _show_window_selector(self):
        """Show the window selector overlay"""
        WindowSelector(self.on_window_selected)

    def on_window_selected(self, hwnd):
        """Called when window selection is complete"""
        self._capture_in_progress = False  # Reset flag
        self.root.deiconify()

        if hwnd is None:
            self.status_var.set("Window capture cancelled")
            return

        self.capture_window(hwnd)

    def capture_window(self, hwnd):
        """Capture a specific window by its handle"""
        import win32gui
        import win32ui
        import win32con
        from ctypes import windll

        try:
            self.status_var.set("Capturing window...")
            self.root.update()

            # Get window rectangle
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            width = right - left
            height = bottom - top

            if width <= 0 or height <= 0:
                self.status_var.set("Invalid window dimensions")
                return

            # Bring window to front briefly to ensure it's visible
            try:
                win32gui.SetForegroundWindow(hwnd)
                time.sleep(0.1)
            except:
                pass

            # Capture using mss (more reliable)
            with mss.mss() as sct:
                monitor = {"top": top, "left": left, "width": width, "height": height}
                screenshot = sct.grab(monitor)
                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

            # Open editor or save directly
            if self.edit_before_save.get():
                self.status_var.set("Edit screenshot (add highlights, then Save or Cancel)")
                ScreenshotEditor(img, self.on_editor_complete)
            else:
                self.save_screenshot(img)

        except Exception as e:
            error_msg = f"Error capturing window: {e}"
            self.status_var.set(error_msg)
            print(error_msg)
            messagebox.showerror("Error", error_msg)

    def start_region_capture(self):
        """Start the region selection process"""
        delay = int(self.delay_var.get())

        if delay > 0:
            # Start countdown, then capture region
            self.status_var.set(f"Countdown: {delay} seconds - set up your screen!")
            self.root.iconify()
            self.root.after(200, lambda: DelayCountdown(delay, self._on_region_delay_complete))
        else:
            # No delay - capture immediately
            self.status_var.set("Select a region...")
            self.root.update()
            self.root.iconify()
            self.root.after(200, self._show_region_selector)

    def _on_region_delay_complete(self, proceed):
        """Called when region delay countdown finishes"""
        if proceed:
            self._show_region_selector()
        else:
            self.root.deiconify()
            self.status_var.set("Capture cancelled")

    def _show_region_selector(self):
        """Show the region selector overlay"""
        RegionSelector(self.on_region_selected)

    def on_region_selected(self, region):
        """Called when region selection is complete"""
        self._capture_in_progress = False  # Reset flag
        # Restore main window
        self.root.deiconify()

        if region is None:
            self.status_var.set("Region capture cancelled")
            return

        # Capture the selected region
        x1, y1, x2, y2 = region
        self.capture_region(x1, y1, x2, y2)

    def capture_region(self, x1, y1, x2, y2):
        """Capture a specific region of the screen"""
        try:
            self.status_var.set("Capturing region...")
            self.root.update()

            # Small delay to ensure overlay is fully gone
            self.root.after(100)

            # Capture the region using mss
            with mss.mss() as sct:
                monitor = {"top": y1, "left": x1, "width": x2 - x1, "height": y2 - y1}
                screenshot = sct.grab(monitor)
                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

            # Open editor or save directly
            if self.edit_before_save.get():
                self.status_var.set("Edit screenshot (add highlights, then Save or Cancel)")
                ScreenshotEditor(img, self.on_editor_complete)
            else:
                self.save_screenshot(img)

        except Exception as e:
            error_msg = f"Error capturing region: {e}"
            self.status_var.set(error_msg)
            print(error_msg)
            messagebox.showerror("Error", error_msg)

    def capture_fullscreen(self):
        """Capture the entire screen"""
        delay = int(self.delay_var.get())

        if delay > 0:
            # Start countdown, then capture
            self.status_var.set(f"Countdown: {delay} seconds - set up your screen!")
            self.root.iconify()
            self.root.after(200, lambda: DelayCountdown(delay, self._on_fullscreen_delay_complete))
        else:
            # No delay - hide window briefly then capture
            self.root.iconify()
            self.root.after(150, self._do_fullscreen_capture)

    def _on_fullscreen_delay_complete(self, proceed):
        """Called when fullscreen delay countdown finishes"""
        if proceed:
            self._do_fullscreen_capture()
        else:
            self._capture_in_progress = False  # Reset flag
            self.root.deiconify()
            self.status_var.set("Capture cancelled")

    def _do_fullscreen_capture(self):
        """Actually capture the fullscreen"""
        self._capture_in_progress = False  # Reset flag
        try:
            self.status_var.set("Capturing...")
            self.root.update()

            # Brief delay to allow any UI to settle
            self.root.after(100)

            # Capture the screen using mss (faster than PIL)
            with mss.mss() as sct:
                # Capture all monitors
                screenshot = sct.grab(sct.monitors[0])  # Monitor 0 = all monitors combined
                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

            # Restore window
            self.root.deiconify()

            # Open editor or save directly
            if self.edit_before_save.get():
                self.status_var.set("Edit screenshot (add highlights, then Save or Cancel)")
                ScreenshotEditor(img, self.on_editor_complete)
            else:
                self.save_screenshot(img)

        except Exception as e:
            self.root.deiconify()
            error_msg = f"Error capturing screenshot: {e}"
            self.status_var.set(error_msg)
            print(error_msg)
            messagebox.showerror("Error", error_msg)

    def on_editor_complete(self, edited_image):
        """Called when editor is done - save if image provided, discard if None"""
        if edited_image is None:
            self.status_var.set("Screenshot discarded")
            return

        # Save the edited image
        self.save_screenshot(edited_image)

    def save_screenshot(self, img):
        """Save a screenshot image to disk and copy to clipboard"""
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"
        filepath = self.save_dir / filename

        # Save the image
        img.save(str(filepath), "PNG")

        # Copy to clipboard for easy pasting
        self.copy_to_clipboard(img)

        # Update counter
        self.screenshot_count += 1
        self.counter_var.set(f"Screenshots this session: {self.screenshot_count}")

        # Update status
        self.status_var.set(f"Saved & copied to clipboard: {filename}")

        # Refresh gallery
        self.refresh_gallery()

        # Flash effect / notification
        self.flash_notification()

        print(f"Screenshot saved: {filepath}")
        print("Image copied to clipboard - ready to paste!")

        # Auto-paste to Claude if enabled
        if self.auto_paste_claude.get():
            self.root.after(200, self.paste_to_vscode_claude)

    def copy_to_clipboard(self, img):
        """Copy image to Windows clipboard using pywin32"""
        import io
        import win32clipboard

        # Convert to RGB if necessary
        if img.mode != 'RGB':
            img = img.convert('RGB')

        # Save as BMP to memory
        output = io.BytesIO()
        img.save(output, 'BMP')
        bmp_data = output.getvalue()
        output.close()

        # Skip BMP file header (14 bytes) to get DIB data
        dib_data = bmp_data[14:]

        # Use win32clipboard (much more reliable than ctypes)
        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, dib_data)
        finally:
            win32clipboard.CloseClipboard()

    def paste_to_vscode_claude(self):
        """Find VSCode window and paste the screenshot into Claude input"""
        try:
            import win32gui
            import win32con

            # Find VSCode window - look for windows with "Visual Studio Code" in title
            vscode_windows = [w for w in gw.getAllWindows()
                           if 'Visual Studio Code' in w.title or 'VSCode' in w.title]

            if not vscode_windows:
                self.status_var.set("VSCode not found - image in clipboard")
                print("Could not find VSCode window")
                return

            # Get the first VSCode window
            vscode = vscode_windows[0]

            # Get the window handle for more reliable activation
            hwnd = vscode._hWnd

            # Restore if minimized
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

            # Bring window to foreground using Windows API (more reliable)
            win32gui.SetForegroundWindow(hwnd)

            # Brief wait for window to come to foreground
            time.sleep(0.2)

            # Just paste - don't try to click anywhere
            # The paste will go to whatever has focus in VSCode
            # User should have Claude input focused (or it will paste to last focused area)
            pyautogui.hotkey('ctrl', 'v')

            self.status_var.set(f"Pasted to VSCode! (Make sure Claude input has focus)")
            print("Screenshot pasted to VSCode")

        except Exception as e:
            error_msg = f"Auto-paste failed: {e}"
            self.status_var.set(f"Saved (auto-paste failed: {e})")
            print(error_msg)

    def flash_notification(self):
        # Brief visual flash to confirm capture
        original_bg = self.root.cget("bg")
        self.root.configure(bg="green")
        self.root.after(100, lambda: self.root.configure(bg=original_bg))

    def get_thumbnail_size(self):
        """Calculate thumbnail size based on scale (1-10)"""
        scale = self.thumbnail_scale.get()
        base_width, base_height = 120, 90  # Default size at scale 5

        # Scale 1 = 50% (0.5x), Scale 5 = 100% (1.0x), Scale 10 = 300% (3.0x)
        if scale <= 5:
            factor = 0.5 + (scale - 1) * 0.5 / 4
        else:
            factor = 1.0 + (scale - 5) * 2.0 / 5

        return (int(base_width * factor), int(base_height * factor))

    def update_disk_usage(self, show_warning=True):
        """Calculate and display total size of screenshots with color coding"""
        try:
            total_bytes = sum(f.stat().st_size for f in self.save_dir.glob("screenshot_*.png"))
            limit_bytes = self.disk_limit_mb.get() * 1024 * 1024
            usage_percent = (total_bytes / limit_bytes * 100) if limit_bytes > 0 else 0

            # Format size nicely
            if total_bytes < 1024:
                size_str = f"{total_bytes} B"
            elif total_bytes < 1024 * 1024:
                size_str = f"{total_bytes / 1024:.1f} KB"
            elif total_bytes < 1024 * 1024 * 1024:
                size_str = f"{total_bytes / (1024 * 1024):.1f} MB"
            else:
                size_str = f"{total_bytes / (1024 * 1024 * 1024):.2f} GB"

            # Show usage with percentage
            limit_mb = self.disk_limit_mb.get()
            self.disk_usage_var.set(f"📁 {size_str} / {limit_mb} MB")

            # Color based on usage percentage
            if usage_percent < 50:
                color = "#228B22"  # Forest green
            elif usage_percent < 70:
                color = "#DAA520"  # Goldenrod (yellow-orange)
            elif usage_percent < 90:
                color = "#FF8C00"  # Dark orange
            else:
                color = "#DC143C"  # Crimson red

            self.disk_label.config(fg=color)

            # Show cleanup prompt at 90% (only once per session or when triggered)
            if show_warning and usage_percent >= 90 and not getattr(self, '_cleanup_prompted', False):
                self._cleanup_prompted = True
                self.root.after(500, self.prompt_cleanup)

        except:
            self.disk_usage_var.set("")

    def prompt_cleanup(self):
        """Prompt user to clean up old screenshots"""
        days = self.archive_days.get()
        result = messagebox.askyesno(
            "Disk Space Warning",
            f"Screenshot storage is over 90% of limit.\n\n"
            f"Would you like to delete screenshots older than {days} days?",
            icon="warning"
        )
        if result:
            self.cleanup_old_screenshots()

    def cleanup_old_screenshots(self):
        """Delete screenshots older than archive_days setting"""
        import datetime
        days = self.archive_days.get()
        cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
        deleted_count = 0
        deleted_bytes = 0

        try:
            for f in self.save_dir.glob("screenshot_*.png"):
                file_time = datetime.datetime.fromtimestamp(f.stat().st_mtime)
                if file_time < cutoff:
                    deleted_bytes += f.stat().st_size
                    f.unlink()
                    deleted_count += 1

            if deleted_count > 0:
                size_mb = deleted_bytes / (1024 * 1024)
                messagebox.showinfo(
                    "Cleanup Complete",
                    f"Deleted {deleted_count} screenshot(s)\n"
                    f"Freed {size_mb:.1f} MB of space"
                )
                self._cleanup_prompted = False  # Allow future prompts
                self.refresh_gallery()
            else:
                messagebox.showinfo(
                    "Cleanup Complete",
                    f"No screenshots older than {days} days found."
                )
        except Exception as e:
            messagebox.showerror("Error", f"Cleanup failed: {e}")

    def manual_cleanup(self):
        """Manually trigger cleanup with confirmation"""
        days = self.archive_days.get()
        result = messagebox.askyesno(
            "Confirm Cleanup",
            f"Delete all screenshots older than {days} days?",
            icon="question"
        )
        if result:
            self.cleanup_old_screenshots()

    def refresh_gallery(self):
        # Update disk usage display
        self.update_disk_usage()

        # Clear existing thumbnails
        for widget in self.gallery_frame.winfo_children():
            widget.destroy()

        # Get list of screenshots
        try:
            screenshots = sorted(
                self.save_dir.glob("screenshot_*.png"),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )[:20]  # Show last 20 screenshots
        except Exception as e:
            print(f"Error reading screenshots: {e}")
            screenshots = []

        if not screenshots:
            no_images_label = ttk.Label(
                self.gallery_frame,
                text="No screenshots yet. Press Ctrl+Shift+R to capture a region!"
            )
            no_images_label.pack(pady=20)
            return

        # Store references to prevent garbage collection
        self.thumbnail_images = []

        # Calculate thumbnails per row based on size
        thumb_width = self.get_thumbnail_size()[0]
        gallery_width = 560  # Approximate usable width
        thumbs_per_row = max(1, gallery_width // (thumb_width + 15))

        # Create thumbnail grid
        row_frame = None
        for i, screenshot_path in enumerate(screenshots):
            if i % thumbs_per_row == 0:
                row_frame = ttk.Frame(self.gallery_frame)
                row_frame.pack(fill=tk.X, pady=5)

            try:
                # Create thumbnail container
                thumb_frame = tk.Frame(row_frame, bg='white')
                thumb_frame.pack(side=tk.LEFT, padx=5)

                # Load and resize image based on thumbnail scale
                img = Image.open(screenshot_path)
                thumb_size = self.get_thumbnail_size()
                img.thumbnail(thumb_size, Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self.thumbnail_images.append(photo)

                # Create container for image and overlay
                img_container = tk.Frame(thumb_frame, bg='white')
                img_container.pack()

                # Create clickable thumbnail
                thumb_label = tk.Label(img_container, image=photo, cursor="hand2", bg='white')
                thumb_label.pack()
                thumb_label.bind("<Button-1>", lambda e, p=screenshot_path: self.open_image(p))

                # Create overlay frame for hover menu - transparent container
                overlay = tk.Frame(img_container)

                # Menu buttons - compact, same width, no border
                btn_style = {'font': ("", 7), 'cursor': "hand2", 'relief': tk.FLAT,
                             'fg': 'white', 'pady': 2, 'bd': 0, 'width': 5,
                             'highlightthickness': 0, 'activeforeground': 'white'}

                btn_open = tk.Button(
                    overlay, text="Open", bg='#4CAF50', activebackground='#45a049', **btn_style,
                    command=lambda p=screenshot_path: self.open_image(p)
                )
                btn_edit = tk.Button(
                    overlay, text="Edit", bg='#9C27B0', activebackground='#7B1FA2', **btn_style,
                    command=lambda p=screenshot_path: self.edit_screenshot(p)
                )
                btn_copy = tk.Button(
                    overlay, text="Copy", bg='#2196F3', activebackground='#1976D2', **btn_style,
                    command=lambda p=screenshot_path: self.copy_file_to_clipboard(p)
                )
                btn_delete = tk.Button(
                    overlay, text="Del", bg='#f44336', activebackground='#d32f2f', **btn_style,
                    command=lambda p=screenshot_path: self.delete_screenshot(p)
                )

                btn_open.pack(pady=1)
                btn_edit.pack(pady=1)
                btn_copy.pack(pady=1)
                btn_delete.pack(pady=1)

                # Hover enter/leave functions - center the buttons
                def on_enter(e, ol=overlay):
                    ol.place(relx=0.5, rely=0.5, anchor='center')

                def on_leave(e, ol=overlay):
                    ol.place_forget()

                # Bind hover events to the container
                img_container.bind("<Enter>", on_enter)
                img_container.bind("<Leave>", on_leave)

                # Filename label
                name_label = ttk.Label(
                    thumb_frame,
                    text=screenshot_path.name[:15] + "...",
                    font=("", 8)
                )
                name_label.pack()

            except Exception as e:
                print(f"Error loading thumbnail {screenshot_path}: {e}")

    def copy_file_to_clipboard(self, filepath):
        """Copy an existing image file to clipboard"""
        try:
            img = Image.open(filepath)
            self.copy_to_clipboard(img)
            self.status_var.set(f"Copied to clipboard: {filepath.name}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not copy image: {e}")

    def delete_screenshot(self, filepath):
        """Delete a screenshot file"""
        if messagebox.askyesno("Delete Screenshot", f"Delete {filepath.name}?"):
            try:
                os.remove(filepath)
                self.status_var.set(f"Deleted: {filepath.name}")
                self.refresh_gallery()
            except Exception as e:
                messagebox.showerror("Error", f"Could not delete: {e}")

    def edit_screenshot(self, filepath):
        """Open an existing screenshot in the editor for annotations"""
        try:
            img = Image.open(filepath)
            self.status_var.set("Edit screenshot (add annotations, then Save or Cancel)")
            ScreenshotEditor(img, self.on_editor_complete)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open image for editing: {e}")

    def open_image(self, filepath):
        """Open image in default system viewer"""
        try:
            os.startfile(str(filepath))
        except Exception as e:
            messagebox.showerror("Error", f"Could not open image: {e}")

    def open_save_folder(self):
        """Open the save folder in file explorer"""
        try:
            os.startfile(str(self.save_dir))
        except Exception as e:
            messagebox.showerror("Error", f"Could not open folder: {e}")

    def show_settings(self):
        """Show the settings dialog"""
        settings_win = tk.Toplevel(self.root)
        settings_win.title("Settings")
        settings_win.transient(self.root)
        settings_win.resizable(False, False)

        # Center on parent
        settings_win.geometry("350x520")
        settings_win.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - settings_win.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - settings_win.winfo_height()) // 2
        settings_win.geometry(f"+{x}+{y}")

        # Main container with padding
        frame = ttk.Frame(settings_win, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        # Capture Mode
        mode_frame = ttk.Frame(frame)
        mode_frame.pack(fill=tk.X, pady=(0, 15))
        ttk.Label(mode_frame, text="Capture Mode:", width=15).pack(side=tk.LEFT)
        mode_combo = ttk.Combobox(
            mode_frame,
            textvariable=self.capture_mode_var,
            values=["Region", "Window", "Full Screen"],
            state="readonly",
            width=15
        )
        mode_combo.pack(side=tk.LEFT, padx=(10, 0))

        # Capture button for manual capture
        capture_btn = ttk.Button(mode_frame, text="Capture", command=self.do_capture, width=8)
        capture_btn.pack(side=tk.LEFT, padx=(10, 0))

        # Delay
        delay_frame = ttk.Frame(frame)
        delay_frame.pack(fill=tk.X, pady=(0, 15))
        ttk.Label(delay_frame, text="Delay (seconds):", width=15).pack(side=tk.LEFT)
        delay_combo = ttk.Combobox(
            delay_frame,
            textvariable=self.delay_var,
            values=["0", "3", "5", "10"],
            state="readonly",
            width=15
        )
        delay_combo.pack(side=tk.LEFT, padx=(10, 0))

        # Checkboxes
        check_frame = ttk.Frame(frame)
        check_frame.pack(fill=tk.X, pady=(0, 15))

        edit_check = ttk.Checkbutton(
            check_frame,
            text="Edit before save (open editor after capture)",
            variable=self.edit_before_save
        )
        edit_check.pack(anchor=tk.W, pady=2)

        paste_check = ttk.Checkbutton(
            check_frame,
            text="Auto-paste to VSCode Claude",
            variable=self.auto_paste_claude
        )
        paste_check.pack(anchor=tk.W, pady=2)

        # Thumbnail size slider
        thumb_frame = ttk.Frame(frame)
        thumb_frame.pack(fill=tk.X, pady=(0, 15))
        ttk.Label(thumb_frame, text="Preview Size:", width=15).pack(side=tk.LEFT)

        # Show current size label
        size_label = ttk.Label(thumb_frame, text="", width=10)

        def update_size_label(*args):
            w, h = self.get_thumbnail_size()
            size_label.config(text=f"{w}x{h}")

        thumb_slider = ttk.Scale(
            thumb_frame,
            from_=1,
            to=10,
            variable=self.thumbnail_scale,
            orient=tk.HORIZONTAL,
            length=120,
            command=update_size_label  # Just update label while dragging
        )
        thumb_slider.pack(side=tk.LEFT, padx=(10, 5))
        # Refresh gallery only when slider is released
        thumb_slider.bind("<ButtonRelease-1>", lambda e: self.refresh_gallery())
        size_label.pack(side=tk.LEFT)
        update_size_label()

        # Storage management section
        storage_frame = ttk.LabelFrame(frame, text="Storage Management", padding="10")
        storage_frame.pack(fill=tk.X, pady=(0, 15))

        # Disk limit
        limit_frame = ttk.Frame(storage_frame)
        limit_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(limit_frame, text="Disk Limit (MB):", width=15).pack(side=tk.LEFT)
        limit_combo = ttk.Combobox(
            limit_frame,
            textvariable=self.disk_limit_mb,
            values=["100", "250", "500", "1000", "2000", "5000"],
            width=10
        )
        limit_combo.pack(side=tk.LEFT, padx=(10, 0))
        limit_combo.bind("<<ComboboxSelected>>", lambda e: self.update_disk_usage(show_warning=False))

        # Archive days
        archive_frame = ttk.Frame(storage_frame)
        archive_frame.pack(fill=tk.X, pady=(5, 5))
        ttk.Label(archive_frame, text="Auto-cleanup age:", width=15).pack(side=tk.LEFT)
        archive_combo = ttk.Combobox(
            archive_frame,
            textvariable=self.archive_days,
            values=["7", "14", "30", "60", "90"],
            width=10
        )
        archive_combo.pack(side=tk.LEFT, padx=(10, 0))
        ttk.Label(archive_frame, text="days").pack(side=tk.LEFT, padx=(5, 0))

        # Manual cleanup button
        cleanup_btn = ttk.Button(
            storage_frame,
            text="Clean Up Now",
            command=self.manual_cleanup
        )
        cleanup_btn.pack(pady=(5, 0))

        # Save location
        loc_frame = ttk.LabelFrame(frame, text="Save Location", padding="10")
        loc_frame.pack(fill=tk.X, pady=(0, 15))

        self.dir_var = tk.StringVar(value=str(self.save_dir))
        dir_label = ttk.Label(loc_frame, textvariable=self.dir_var, wraplength=280)
        dir_label.pack(fill=tk.X, pady=(0, 10))

        btn_frame = ttk.Frame(loc_frame)
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="Change...", command=self.change_save_dir).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(btn_frame, text="Open Folder", command=self.open_save_folder).pack(side=tk.LEFT)

        # Close button
        ttk.Button(frame, text="Close", command=settings_win.destroy).pack(pady=(10, 0))

    def change_save_dir(self):
        """Change the save directory"""
        new_dir = filedialog.askdirectory(
            initialdir=str(self.save_dir),
            title="Select Screenshot Save Location"
        )
        if new_dir:
            self.save_dir = Path(new_dir)
            self.dir_var.set(str(self.save_dir))
            self.refresh_gallery()
            self.status_var.set(f"Save location changed to: {new_dir}")

    def on_close(self):
        """Clean up and close"""
        self.unregister_hotkeys()
        self.root.destroy()

    def run(self):
        """Start the application"""
        print("Screenshot Tool started!")
        print(f"Screenshots will be saved to: {self.save_dir}")
        print(f"Hotkeys:")
        print(f"  {self.hotkey_region} - Capture region")
        print(f"  {self.hotkey_full} - Capture full screen")
        print(f"\nTip: Enable 'Auto-paste to VSCode Claude' to automatically send screenshots to Claude!")
        self.root.mainloop()


if __name__ == "__main__":
    app = ScreenshotTool()
    app.run()
