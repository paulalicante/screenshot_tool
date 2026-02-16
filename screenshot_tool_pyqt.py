"""
Otterly Screenshots - PyQt6 Version
A modern Windows screenshot utility with Solarized Light theme

Features:
- Global hotkeys (Ctrl+Shift+S/R/W) for screen, region, window capture
- Gallery with folder organization and drag-drop
- Screenshot editor with highlight, circle, and text tools
- Toast notifications and auto-send to apps
"""

import sys
import os
import json
import shutil
import logging
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from io import BytesIO
import ctypes
import struct

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QSplitter, QScrollArea,
    QSlider, QComboBox, QCheckBox, QDialog, QLineEdit,
    QMessageBox, QFileDialog, QMenu, QGridLayout, QSizePolicy,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
    QInputDialog, QToolBar, QSpinBox, QListWidget, QListWidgetItem,
    QToolButton
)
from PyQt6.QtCore import (
    Qt, QPoint, QTimer, QSize, QRect, QThread, pyqtSignal,
    QMimeData, QUrl, QPropertyAnimation, QEasingCurve
)
from PyQt6.QtGui import (
    QFont, QMouseEvent, QPixmap, QImage, QPainter, QPen, QBrush,
    QColor, QCursor, QDrag, QIcon, QPainterPath, QFontMetrics,
    QWheelEvent, QKeyEvent
)

# External dependencies
try:
    from PIL import Image, ImageGrab
except ImportError:
    print("Installing Pillow...")
    os.system(f"{sys.executable} -m pip install Pillow --quiet")
    from PIL import Image, ImageGrab

try:
    import keyboard
except ImportError:
    print("Installing keyboard...")
    os.system(f"{sys.executable} -m pip install keyboard --quiet")
    import keyboard

try:
    import mss
except ImportError:
    print("Installing mss...")
    os.system(f"{sys.executable} -m pip install mss --quiet")
    import mss

try:
    import pyautogui
except ImportError:
    print("Installing pyautogui...")
    os.system(f"{sys.executable} -m pip install pyautogui --quiet")
    import pyautogui

# Win32 imports for window management and clipboard
try:
    import win32gui
    import win32con
    import win32clipboard
    import win32ui
except ImportError:
    print("Installing pywin32...")
    os.system(f"{sys.executable} -m pip install pywin32 --quiet")
    import win32gui
    import win32con
    import win32clipboard
    import win32ui

# Optional: Virtual desktop support
try:
    from pyvda import AppView, VirtualDesktop
    PYVDA_AVAILABLE = True
except ImportError:
    PYVDA_AVAILABLE = False

# ============================================================================
# CONSTANTS & THEME
# ============================================================================

APP_NAME = "Otterly Screenshots"
APP_VERSION = "2.0"

# Theme Presets
THEMES = {
    'solarized_dark': {
        'name': 'Solarized Dark',
        'BG_LIGHT': '#FDF6E3',
        'BG_CONTENT': '#EEE8D5',
        'BG_DARK': '#073642',
        'BG_DARKER': '#002B36',
        'BG_SIDEBAR': '#073642',
        'BG_GALLERY': '#073642',
        'BG_TITLEBAR': '#073642',
        'TEXT_DARK': '#073642',
        'TEXT_MUTED': '#93A1A1',
        'TEXT_LIGHT': '#FDF6E3',
        'TEXT_GRAY': '#657B83',
        'TEXT_TITLEBAR': '#FDF6E3',
        'TEXT_SIDEBAR': '#93A1A1',
        'TEXT_GALLERY': '#FDF6E3',
        'ACCENT': '#268BD2',
        'SUCCESS': '#859900',
        'WARNING': '#CB4B16',
        'ERROR': '#DC322F',
        'BORDER': '#002B36',
        'BUTTON_BG': '#586E75',
        'BUTTON_TEXT': '#FDF6E3',
        'BUTTON_HOVER': '#657B83',
    },
    'warm_contrast': {
        'name': 'Warm Contrast',
        'BG_LIGHT': '#FDF6E3',
        'BG_CONTENT': '#EEE8D5',
        'BG_DARK': '#073642',
        'BG_DARKER': '#002B36',
        'BG_SIDEBAR': '#FDF6E3',
        'BG_GALLERY': '#073642',
        'BG_TITLEBAR': '#FDF6E3',
        'TEXT_DARK': '#073642',
        'TEXT_MUTED': '#657B83',
        'TEXT_LIGHT': '#FDF6E3',
        'TEXT_GRAY': '#657B83',
        'TEXT_TITLEBAR': '#073642',
        'TEXT_SIDEBAR': '#073642',
        'TEXT_GALLERY': '#FDF6E3',
        'ACCENT': '#D79921',
        'SUCCESS': '#859900',
        'WARNING': '#CB4B16',
        'ERROR': '#DC322F',
        'BORDER': '#D3CBB7',
        'BUTTON_BG': '#D79921',
        'BUTTON_TEXT': '#ffffff',
        'BUTTON_HOVER': '#B58900',
    },
    'charcoal': {
        'name': 'Charcoal',
        'BG_LIGHT': '#3d3d3d',
        'BG_CONTENT': '#2d2d2d',
        'BG_DARK': '#1a1a1a',
        'BG_DARKER': '#111111',
        'BG_SIDEBAR': '#1a1a1a',
        'BG_GALLERY': '#1a1a1a',
        'BG_TITLEBAR': '#1a1a1a',
        'TEXT_DARK': '#e0e0e0',
        'TEXT_MUTED': '#888888',
        'TEXT_LIGHT': '#e0e0e0',
        'TEXT_GRAY': '#aaaaaa',
        'TEXT_TITLEBAR': '#e0e0e0',
        'TEXT_SIDEBAR': '#e0e0e0',
        'TEXT_GALLERY': '#e0e0e0',
        'ACCENT': '#6B9FCE',
        'SUCCESS': '#7CB342',
        'WARNING': '#FFA726',
        'ERROR': '#EF5350',
        'BORDER': '#333333',
        'BUTTON_BG': '#2d2d2d',
        'BUTTON_TEXT': '#e0e0e0',
        'BUTTON_HOVER': '#3d3d3d',
    },
    'midnight': {
        'name': 'Midnight Blue',
        'BG_LIGHT': '#2c3e50',
        'BG_CONTENT': '#243342',
        'BG_DARK': '#1a252f',
        'BG_DARKER': '#151d25',
        'BG_SIDEBAR': '#1a252f',
        'BG_GALLERY': '#1a252f',
        'BG_TITLEBAR': '#1a252f',
        'TEXT_DARK': '#ecf0f1',
        'TEXT_MUTED': '#7f8c8d',
        'TEXT_LIGHT': '#ecf0f1',
        'TEXT_GRAY': '#95a5a6',
        'TEXT_TITLEBAR': '#ecf0f1',
        'TEXT_SIDEBAR': '#ecf0f1',
        'TEXT_GALLERY': '#ecf0f1',
        'ACCENT': '#3498db',
        'SUCCESS': '#2ecc71',
        'WARNING': '#f39c12',
        'ERROR': '#e74c3c',
        'BORDER': '#243342',
        'BUTTON_BG': '#2c3e50',
        'BUTTON_TEXT': '#ecf0f1',
        'BUTTON_HOVER': '#34495e',
    },
    'light': {
        'name': 'Light',
        'BG_LIGHT': '#ffffff',
        'BG_CONTENT': '#f5f5f5',
        'BG_DARK': '#e8e8e8',
        'BG_DARKER': '#d0d0d0',
        'BG_SIDEBAR': '#f0f0f0',
        'BG_GALLERY': '#ffffff',
        'BG_TITLEBAR': '#f0f0f0',
        'TEXT_DARK': '#333333',
        'TEXT_MUTED': '#666666',
        'TEXT_LIGHT': '#ffffff',
        'TEXT_GRAY': '#888888',
        'TEXT_TITLEBAR': '#333333',
        'TEXT_SIDEBAR': '#333333',
        'TEXT_GALLERY': '#333333',
        'ACCENT': '#2196F3',
        'SUCCESS': '#4CAF50',
        'WARNING': '#FF9800',
        'ERROR': '#f44336',
        'BORDER': '#dddddd',
        'BUTTON_BG': '#2196F3',
        'BUTTON_TEXT': '#ffffff',
        'BUTTON_HOVER': '#1976D2',
    },
}

# Active theme storage
_active_theme = 'solarized_dark'

def get_theme_names() -> list:
    """Get list of available theme names"""
    return [(k, v['name']) for k, v in THEMES.items()]

def set_active_theme(theme_key: str):
    """Set the active theme"""
    global _active_theme
    if theme_key in THEMES:
        _active_theme = theme_key

def get_active_theme() -> str:
    """Get the active theme key"""
    return _active_theme


class Theme:
    """Dynamic theme class that reads from active theme preset"""

    @staticmethod
    def _get(key: str) -> str:
        return THEMES[_active_theme].get(key, '#FF00FF')  # Magenta for missing

    @property
    def BG_LIGHT(self): return self._get('BG_LIGHT')
    @property
    def BG_CONTENT(self): return self._get('BG_CONTENT')
    @property
    def BG_DARK(self): return self._get('BG_DARK')
    @property
    def BG_DARKER(self): return self._get('BG_DARKER')
    @property
    def BG_SIDEBAR(self): return self._get('BG_SIDEBAR')
    @property
    def BG_GALLERY(self): return self._get('BG_GALLERY')
    @property
    def BG_TITLEBAR(self): return self._get('BG_TITLEBAR')
    @property
    def TEXT_DARK(self): return self._get('TEXT_DARK')
    @property
    def TEXT_MUTED(self): return self._get('TEXT_MUTED')
    @property
    def TEXT_LIGHT(self): return self._get('TEXT_LIGHT')
    @property
    def TEXT_GRAY(self): return self._get('TEXT_GRAY')
    @property
    def TEXT_TITLEBAR(self): return self._get('TEXT_TITLEBAR')
    @property
    def TEXT_SIDEBAR(self): return self._get('TEXT_SIDEBAR')
    @property
    def TEXT_GALLERY(self): return self._get('TEXT_GALLERY')
    @property
    def ACCENT(self): return self._get('ACCENT')
    @property
    def SUCCESS(self): return self._get('SUCCESS')
    @property
    def WARNING(self): return self._get('WARNING')
    @property
    def ERROR(self): return self._get('ERROR')
    @property
    def BORDER(self): return self._get('BORDER')
    @property
    def BUTTON_BG(self): return self._get('BUTTON_BG')
    @property
    def BUTTON_TEXT(self): return self._get('BUTTON_TEXT')
    @property
    def BUTTON_HOVER(self): return self._get('BUTTON_HOVER')

    # Highlight colors (same for all themes)
    HIGHLIGHT_YELLOW = (255, 255, 0, 100)
    HIGHLIGHT_GREEN = (0, 255, 0, 100)
    HIGHLIGHT_BLUE = (0, 150, 255, 100)
    HIGHLIGHT_RED = (255, 0, 0, 100)

# Create theme instance
Theme = Theme()


# Paths
SAVE_DIR = Path.home() / "Pictures" / "Screenshots"
CONFIG_FILE = SAVE_DIR / "screenshot_tool_config.json"

# Set up logging
SAVE_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=SAVE_DIR / "screenshot_tool_crash.log",
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


# ============================================================================
# STYLESHEETS
# ============================================================================

def generate_stylesheet() -> str:
    """Generate main stylesheet based on active theme"""
    t = THEMES[_active_theme]
    return f"""
QWidget {{
    font-family: 'Segoe UI';
    font-size: 10pt;
}}

QMainWindow {{
    background: {t['BG_GALLERY']};
}}

/* Sidebar */
#sidebar {{
    background: {t['BG_SIDEBAR']};
    border-right: 1px solid {t['BORDER']};
}}

#sidebar QLabel {{
    color: {t['TEXT_SIDEBAR']};
    background: transparent;
}}

#sidebar QPushButton {{
    background: {t['BUTTON_BG']};
    color: {t['BUTTON_TEXT']};
    border: none;
    border-radius: 6px;
    padding: 10px 16px;
    text-align: left;
    font-size: 10pt;
}}

#sidebar QPushButton:hover {{
    background: {t['BUTTON_HOVER']};
}}

#sidebar QPushButton:pressed {{
    background: {t['ACCENT']};
}}

/* Gallery area */
#gallery {{
    background: {t['BG_GALLERY']};
}}

#gallery QScrollArea {{
    background: {t['BG_GALLERY']};
    border: none;
}}

/* Folder bar */
#folderBar {{
    background: {t['BG_GALLERY']};
    border-bottom: 1px solid {t['BORDER']};
}}

/* Title bar */
#titleBar {{
    background: {t['BG_TITLEBAR']};
    border-bottom: 1px solid {t['BORDER']};
}}

/* Status bar */
#statusBar {{
    background: {t['BG_SIDEBAR']};
    color: {t['TEXT_MUTED']};
    padding: 5px 10px;
}}

/* Scrollbars */
QScrollBar:vertical {{
    background: {t['BG_GALLERY']};
    width: 12px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: {t['TEXT_MUTED']};
    min-height: 30px;
    border-radius: 6px;
    margin: 2px;
}}

QScrollBar::handle:vertical:hover {{
    background: {t['BUTTON_HOVER']};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background: {t['BG_GALLERY']};
    height: 12px;
    margin: 0;
}}

QScrollBar::handle:horizontal {{
    background: {t['TEXT_MUTED']};
    min-width: 30px;
    border-radius: 6px;
    margin: 2px;
}}

QScrollBar::handle:horizontal:hover {{
    background: {t['BUTTON_HOVER']};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* Combo box */
QComboBox {{
    background: {t['BG_LIGHT']};
    border: 1px solid {t['BORDER']};
    border-radius: 4px;
    padding: 5px 10px;
    color: {t['TEXT_DARK']};
}}

QComboBox:hover {{
    border-color: {t['ACCENT']};
}}

QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

QComboBox QAbstractItemView {{
    background: {t['BG_LIGHT']};
    border: 1px solid {t['BORDER']};
    selection-background-color: {t['ACCENT']};
    selection-color: white;
}}

/* Checkbox */
QCheckBox {{
    color: {t['TEXT_DARK']};
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 3px;
    border: 2px solid {t['TEXT_MUTED']};
    background: {t['BG_LIGHT']};
}}

QCheckBox::indicator:checked {{
    background: {t['ACCENT']};
    border-color: {t['ACCENT']};
}}

/* Slider */
QSlider::groove:horizontal {{
    height: 6px;
    background: {t['BORDER']};
    border-radius: 3px;
}}

QSlider::handle:horizontal {{
    width: 16px;
    height: 16px;
    margin: -5px 0;
    background: {t['ACCENT']};
    border-radius: 8px;
}}

QSlider::handle:horizontal:hover {{
    background: {t['SUCCESS']};
}}

/* Line edit */
QLineEdit {{
    background: {t['BG_LIGHT']};
    border: 1px solid {t['BORDER']};
    border-radius: 4px;
    padding: 6px 10px;
    color: {t['TEXT_DARK']};
}}

QLineEdit:focus {{
    border-color: {t['ACCENT']};
}}

/* List widget */
QListWidget {{
    background: {t['BG_LIGHT']};
    border: 1px solid {t['BORDER']};
    border-radius: 4px;
}}

QListWidget::item {{
    padding: 8px;
    border-bottom: 1px solid {t['BG_CONTENT']};
}}

QListWidget::item:selected {{
    background: {t['ACCENT']};
    color: white;
}}

QListWidget::item:hover {{
    background: {t['BG_CONTENT']};
}}
"""


# ============================================================================
# CUSTOM TITLE BAR
# ============================================================================

class CustomTitleBar(QWidget):
    """Custom title bar for frameless window with drag support"""

    def __init__(self, parent, title: str = APP_NAME, show_logo: bool = True):
        super().__init__(parent)
        self.parent_window = parent
        self.dragging = False
        self.drag_position = QPoint()

        self.setObjectName("titleBar")
        self.setFixedHeight(40)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 5, 0)
        layout.setSpacing(10)

        # Logo (optional)
        if show_logo:
            self.logo_label = QLabel()
            logo_path = Path(__file__).parent / "logo.png"
            if logo_path.exists():
                logo_pixmap = QPixmap(str(logo_path))
                scaled = logo_pixmap.scaled(28, 28, Qt.AspectRatioMode.KeepAspectRatio,
                                           Qt.TransformationMode.SmoothTransformation)
                self.logo_label.setPixmap(scaled)
            self.logo_label.setStyleSheet("background: transparent;")
            layout.addWidget(self.logo_label)

        # Title
        self.title_label = QLabel(title)
        self.title_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.title_label.setStyleSheet(f"color: {Theme.TEXT_TITLEBAR}; background: transparent;")
        layout.addWidget(self.title_label)

        layout.addStretch()

        # Window control buttons
        btn_style = f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {Theme.TEXT_TITLEBAR};
                font-size: 16px;
                font-weight: bold;
                min-width: 40px;
                max-width: 40px;
                min-height: 35px;
                max-height: 35px;
            }}
            QPushButton:hover {{
                background: {Theme.BUTTON_BG};
                color: {Theme.TEXT_LIGHT};
            }}
        """

        close_style = f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {Theme.TEXT_TITLEBAR};
                font-size: 16px;
                font-weight: bold;
                min-width: 40px;
                max-width: 40px;
                min-height: 35px;
                max-height: 35px;
            }}
            QPushButton:hover {{
                background: {Theme.ERROR};
                color: white;
            }}
        """

        # Minimize button
        self.btn_minimize = QPushButton("−")
        self.btn_minimize.setStyleSheet(btn_style)
        self.btn_minimize.clicked.connect(parent.showMinimized)
        layout.addWidget(self.btn_minimize)

        # Maximize button
        self.btn_maximize = QPushButton("□")
        self.btn_maximize.setStyleSheet(btn_style)
        self.btn_maximize.clicked.connect(self._toggle_maximize)
        layout.addWidget(self.btn_maximize)

        # Close button
        self.btn_close = QPushButton("×")
        self.btn_close.setStyleSheet(close_style)
        self.btn_close.clicked.connect(parent.close)
        layout.addWidget(self.btn_close)

    def _toggle_maximize(self):
        if self.parent_window.isMaximized():
            self.parent_window.showNormal()
            self.btn_maximize.setText("□")
        else:
            self.parent_window.showMaximized()
            self.btn_maximize.setText("❐")

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.drag_position = event.globalPosition().toPoint() - self.parent_window.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.dragging and event.buttons() == Qt.MouseButton.LeftButton:
            self.parent_window.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.dragging = False

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        self._toggle_maximize()


# ============================================================================
# DELAY COUNTDOWN WINDOW
# ============================================================================

class DelayCountdown(QWidget):
    """Floating countdown window before capture"""

    countdown_complete = pyqtSignal()
    countdown_cancelled = pyqtSignal()

    def __init__(self, seconds: int):
        super().__init__()
        self.seconds_left = seconds

        # Frameless, always on top
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )

        self.setFixedSize(150, 100)
        self.setStyleSheet(f"background: {Theme.BG_DARKER}; border-radius: 10px;")

        # Position top-right
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - 170, 20)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Countdown number
        self.count_label = QLabel(str(seconds))
        self.count_label.setFont(QFont("Arial", 36, QFont.Weight.Bold))
        self.count_label.setStyleSheet("color: white; background: transparent;")
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.count_label)

        # Info text
        info_label = QLabel("Set up your screen...")
        info_label.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 9pt; background: transparent;")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info_label)

        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BUTTON_BG};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px 10px;
                font-size: 9pt;
            }}
            QPushButton:hover {{
                background: {Theme.BUTTON_HOVER};
            }}
        """)
        cancel_btn.clicked.connect(self._cancel)
        layout.addWidget(cancel_btn)

        # Timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000)

    def _tick(self):
        self.seconds_left -= 1

        if self.seconds_left <= 0:
            self.timer.stop()
            self.close()
            self.countdown_complete.emit()
            return

        self.count_label.setText(str(self.seconds_left))

        # Color change
        if self.seconds_left <= 2:
            self.count_label.setStyleSheet("color: #ff5555; background: transparent;")
        elif self.seconds_left <= 3:
            self.count_label.setStyleSheet("color: #ffaa00; background: transparent;")

    def _cancel(self):
        self.timer.stop()
        self.close()
        self.countdown_cancelled.emit()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self._cancel()


# ============================================================================
# REGION SELECTOR
# ============================================================================

class RegionSelector(QWidget):
    """Fullscreen overlay for selecting a region to capture"""

    region_selected = pyqtSignal(QRect, QPixmap)
    cancelled = pyqtSignal()

    def __init__(self):
        super().__init__()

        # Capture screen FIRST before showing overlay
        self.captured_pixmap = self._capture_screen()

        # Fullscreen frameless overlay
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )

        # Cover all monitors
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)

        self.start_point = None
        self.current_rect = QRect()
        self.setCursor(Qt.CursorShape.CrossCursor)

        self.setMouseTracking(True)

    def _capture_screen(self) -> QPixmap:
        """Capture the entire screen using mss"""
        with mss.mss() as sct:
            monitor = sct.monitors[0]  # All monitors
            screenshot = sct.grab(monitor)
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

            # Convert PIL to QPixmap
            data = img.tobytes("raw", "RGB")
            qimage = QImage(data, img.width, img.height, img.width * 3, QImage.Format.Format_RGB888)
            return QPixmap.fromImage(qimage)

    def paintEvent(self, event):
        painter = QPainter(self)

        # Draw captured image
        painter.drawPixmap(0, 0, self.captured_pixmap)

        # Dark overlay
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))

        # If selecting, show clear region
        if not self.current_rect.isNull() and self.current_rect.width() > 0 and self.current_rect.height() > 0:
            # Draw the selected region without overlay (clear it)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            painter.drawPixmap(self.current_rect, self.captured_pixmap, self.current_rect)

            # Selection border
            painter.setPen(QPen(QColor(Theme.ACCENT), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.current_rect)

            # Dimensions text
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont("Segoe UI", 10))
            text = f"{self.current_rect.width()} × {self.current_rect.height()}"
            text_pos = self.current_rect.bottomRight() + QPoint(5, 15)

            # Background for text
            fm = QFontMetrics(painter.font())
            text_rect = fm.boundingRect(text)
            bg_rect = QRect(text_pos.x() - 2, text_pos.y() - text_rect.height(),
                           text_rect.width() + 4, text_rect.height() + 4)
            painter.fillRect(bg_rect, QColor(0, 0, 0, 150))
            painter.drawText(text_pos, text)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_point = event.pos()
            self.current_rect = QRect()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.start_point:
            self.current_rect = QRect(self.start_point, event.pos()).normalized()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self.current_rect.width() > 10 and self.current_rect.height() > 10:
            cropped = self.captured_pixmap.copy(self.current_rect)
            self.region_selected.emit(self.current_rect, cropped)
        else:
            self.cancelled.emit()
        self.close()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            self.close()


# ============================================================================
# WINDOW SELECTOR
# ============================================================================

class WindowSelector(QWidget):
    """Fullscreen overlay for clicking to select a window"""

    window_selected = pyqtSignal(int)  # HWND
    cancelled = pyqtSignal()

    def __init__(self):
        super().__init__()

        # Fullscreen semi-transparent overlay
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )

        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)

        self.setStyleSheet("background: rgba(0, 0, 0, 50);")
        self.setCursor(Qt.CursorShape.CrossCursor)

        # Info window
        self.info_window = QLabel("Click on a window to capture it\nPress ESC to cancel")
        self.info_window.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.info_window.setStyleSheet(f"""
            background: {Theme.BG_DARKER};
            color: white;
            padding: 15px 25px;
            border-radius: 8px;
            font-size: 11pt;
        """)
        self.info_window.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_window.adjustSize()

        # Position info window at top center
        self.info_window.move(
            screen.width() // 2 - self.info_window.width() // 2,
            50
        )
        self.info_window.show()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            # Get window under cursor
            pos = event.globalPosition().toPoint()
            hwnd = win32gui.WindowFromPoint((pos.x(), pos.y()))

            # Get top-level parent
            root_hwnd = win32gui.GetAncestor(hwnd, win32con.GA_ROOT)

            self.info_window.close()
            self.close()
            self.window_selected.emit(root_hwnd)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self.info_window.close()
            self.close()
            self.cancelled.emit()


# ============================================================================
# TOAST NOTIFICATION
# ============================================================================

class ToastNotification(QWidget):
    """Fade in/out notification at bottom-right"""

    def __init__(self, pixmap: QPixmap, filename: str):
        super().__init__()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Container with styling
        container = QFrame(self)
        container.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_DARKER};
                border-radius: 8px;
            }}
        """)

        layout = QHBoxLayout(container)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        # Thumbnail
        thumb = pixmap.scaled(50, 50, Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
        thumb_label = QLabel()
        thumb_label.setPixmap(thumb)
        thumb_label.setStyleSheet("background: transparent;")
        layout.addWidget(thumb_label)

        # Text
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        saved_label = QLabel("✓ Saved!")
        saved_label.setStyleSheet(f"color: {Theme.SUCCESS}; font-weight: bold; font-size: 11pt; background: transparent;")
        text_layout.addWidget(saved_label)

        file_label = QLabel(filename)
        file_label.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 9pt; background: transparent;")
        text_layout.addWidget(file_label)

        layout.addLayout(text_layout)

        # Size and position
        container.adjustSize()
        self.setFixedSize(container.size())

        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - self.width() - 20,
                  screen.height() - self.height() - 60)

        # Fade in animation
        self.setWindowOpacity(0.0)
        self.fade_in = QPropertyAnimation(self, b"windowOpacity")
        self.fade_in.setDuration(200)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)

        # Fade out animation
        self.fade_out = QPropertyAnimation(self, b"windowOpacity")
        self.fade_out.setDuration(300)
        self.fade_out.setStartValue(1.0)
        self.fade_out.setEndValue(0.0)
        self.fade_out.finished.connect(self.close)

        # Start
        self.show()
        self.fade_in.start()
        QTimer.singleShot(2000, self.fade_out.start)


# ============================================================================
# THUMBNAIL WIDGET
# ============================================================================

class ThumbnailWidget(QFrame):
    """Clickable thumbnail with drag-drop support"""

    clicked = pyqtSignal(Path)
    double_clicked = pyqtSignal(Path)
    context_menu_requested = pyqtSignal(Path, QPoint)

    def __init__(self, filepath: Path, size: QSize):
        super().__init__()
        self.filepath = filepath
        self._drag_start_pos = None

        self.setFixedSize(size.width() + 10, size.height() + 10)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BUTTON_BG};
                border: 1px solid {Theme.BUTTON_HOVER};
                border-radius: 4px;
            }}
            QFrame:hover {{
                border: 2px solid {Theme.ACCENT};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        # Load and scale image
        pixmap = QPixmap(str(filepath))
        if not pixmap.isNull():
            scaled = pixmap.scaled(size, Qt.AspectRatioMode.KeepAspectRatio,
                                  Qt.TransformationMode.SmoothTransformation)
            self.thumb_label = QLabel()
            self.thumb_label.setPixmap(scaled)
            self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.thumb_label.setStyleSheet("background: transparent;")
            layout.addWidget(self.thumb_label)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()
        elif event.button() == Qt.MouseButton.RightButton:
            self.context_menu_requested.emit(self.filepath, event.globalPosition().toPoint())

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drag_start_pos and event.buttons() & Qt.MouseButton.LeftButton:
            if (event.pos() - self._drag_start_pos).manhattanLength() > 10:
                # Start drag
                drag = QDrag(self)
                mime = QMimeData()
                mime.setUrls([QUrl.fromLocalFile(str(self.filepath))])
                drag.setMimeData(mime)
                drag.setPixmap(self.grab().scaled(60, 60, Qt.AspectRatioMode.KeepAspectRatio))
                drag.exec(Qt.DropAction.MoveAction)
                self._drag_start_pos = None

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self._drag_start_pos:
            self.clicked.emit(self.filepath)
        self._drag_start_pos = None

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        self.double_clicked.emit(self.filepath)


# ============================================================================
# FOLDER BUTTON
# ============================================================================

class FolderButton(QFrame):
    """Folder button with preview thumbnails"""

    clicked = pyqtSignal(object)  # folder name or None
    context_menu_requested = pyqtSignal(object, QPoint)
    file_dropped = pyqtSignal(object, Path)  # folder, source file

    def __init__(self, folder_name: Optional[str], base_dir: Path, selected: bool = False):
        super().__init__()
        self.folder_name = folder_name
        self.base_dir = base_dir
        self.selected = selected

        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumWidth(80)
        self.setMaximumWidth(120)

        self._update_style()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # Preview thumbnails row
        preview_layout = QHBoxLayout()
        preview_layout.setSpacing(2)

        folder_path = base_dir / folder_name if folder_name else base_dir
        if folder_path.exists():
            images = sorted(
                [f for f in folder_path.glob("*.png") if f.is_file()],
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )[:3]

            for img_path in images:
                thumb = QLabel()
                pixmap = QPixmap(str(img_path))
                if not pixmap.isNull():
                    scaled = pixmap.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation)
                    thumb.setPixmap(scaled)
                    thumb.setStyleSheet("background: transparent;")
                    preview_layout.addWidget(thumb)

        preview_layout.addStretch()
        layout.addLayout(preview_layout)

        # Folder name
        name_label = QLabel(folder_name or "All")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setStyleSheet(f"""
            color: {Theme.BUTTON_TEXT};
            font-size: 9pt;
            background: transparent;
        """)
        layout.addWidget(name_label)

    def _update_style(self):
        if self.selected:
            self.setStyleSheet(f"""
                QFrame {{
                    background: {Theme.ACCENT};
                    border-radius: 6px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QFrame {{
                    background: {Theme.BUTTON_BG};
                    border: 1px solid {Theme.BUTTON_HOVER};
                    border-radius: 6px;
                }}
                QFrame:hover {{
                    background: {Theme.BUTTON_HOVER};
                    border-color: {Theme.ACCENT};
                }}
            """)

    def set_selected(self, selected: bool):
        self.selected = selected
        self._update_style()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.folder_name)
        elif event.button() == Qt.MouseButton.RightButton:
            if self.folder_name:  # Don't show context menu for "All"
                self.context_menu_requested.emit(self.folder_name, event.globalPosition().toPoint())

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            self.setStyleSheet(f"""
                QFrame {{
                    background: {Theme.SUCCESS};
                    border-radius: 6px;
                }}
            """)
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self._update_style()

    def dropEvent(self, event):
        self._update_style()
        urls = event.mimeData().urls()
        for url in urls:
            source = Path(url.toLocalFile())
            if source.suffix.lower() == '.png':
                self.file_dropped.emit(self.folder_name, source)
        event.acceptProposedAction()


# ============================================================================
# SCREENSHOT EDITOR
# ============================================================================

class ScreenshotEditor(QMainWindow):
    """Screenshot annotation editor with highlight, circle, and text tools"""

    editing_complete = pyqtSignal(QPixmap)
    editing_cancelled = pyqtSignal()

    COLORS = {
        'yellow': QColor(255, 255, 0, 100),
        'green': QColor(0, 255, 0, 100),
        'blue': QColor(0, 150, 255, 100),
        'red': QColor(255, 0, 0, 100),
    }

    def __init__(self, pixmap: QPixmap):
        super().__init__()

        self.original_pixmap = pixmap
        self.current_color = self.COLORS['yellow']
        self.brush_size = 20
        self.draw_mode = 'highlight'  # highlight, circle, text
        self.straight_line = False
        self.drawing = False
        self.last_point = None

        # Create overlay for drawings
        self.overlay_pixmap = QPixmap(pixmap.size())
        self.overlay_pixmap.fill(Qt.GlobalColor.transparent)

        # Preview layer for shapes being drawn
        self.preview_pixmap = QPixmap(pixmap.size())
        self.preview_pixmap.fill(Qt.GlobalColor.transparent)

        self._setup_ui()

    def _setup_ui(self):
        # Frameless window
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        # Size to fit image with toolbar
        img_size = self.original_pixmap.size()
        screen = QApplication.primaryScreen().geometry()

        # Minimum window size to ensure toolbar is always visible
        min_window_w = 800
        min_window_h = 200
        toolbar_height = 80  # Space for toolbar + margins

        # Maximum size (screen minus margins)
        max_w = screen.width() - 100
        max_h = screen.height() - 150

        # Scale image if too large for screen
        scale = min(1.0, max_w / img_size.width(), (max_h - toolbar_height) / img_size.height())
        self.display_size = QSize(int(img_size.width() * scale), int(img_size.height() * scale))
        self.scale_factor = scale

        # Window size: at least minimum, or larger if image requires it
        window_w = max(min_window_w, self.display_size.width() + 20)
        window_h = max(min_window_h, self.display_size.height() + toolbar_height)

        # Don't exceed screen size
        window_w = min(window_w, max_w)
        window_h = min(window_h, max_h)

        self.setFixedSize(window_w, window_h)

        # Center on screen
        self.move(
            (screen.width() - self.width()) // 2,
            (screen.height() - self.height()) // 2
        )

        # Main container
        container = QWidget()
        container.setStyleSheet(f"background: {Theme.BG_CONTENT};")
        self.setCentralWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Toolbar
        toolbar = QFrame()
        toolbar.setStyleSheet(f"background: {Theme.BG_LIGHT}; border-radius: 6px;")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(10, 8, 10, 8)
        toolbar_layout.setSpacing(8)

        # Color buttons
        self.color_buttons = {}
        for name, color in self.COLORS.items():
            btn = QPushButton()
            btn.setFixedSize(30, 30)
            # Use fully opaque color for button
            opaque_color = QColor(color.red(), color.green(), color.blue())
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {opaque_color.name()};
                    border: 2px solid {Theme.TEXT_DARK};
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    border-width: 3px;
                }}
            """)
            btn.clicked.connect(lambda checked, c=color, n=name: self._set_color(c, n))
            toolbar_layout.addWidget(btn)
            self.color_buttons[name] = btn

        toolbar_layout.addSpacing(15)

        # Mode buttons
        mode_style = f"""
            QPushButton {{
                background: {Theme.BG_CONTENT};
                color: {Theme.TEXT_DARK};
                border: 1px solid {Theme.BORDER};
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 10pt;
            }}
            QPushButton:hover {{
                background: {Theme.BORDER};
            }}
            QPushButton:checked {{
                background: {Theme.ACCENT};
                color: white;
                border-color: {Theme.ACCENT};
            }}
        """

        self.highlight_btn = QPushButton("Highlight")
        self.highlight_btn.setCheckable(True)
        self.highlight_btn.setChecked(True)
        self.highlight_btn.setStyleSheet(mode_style)
        self.highlight_btn.clicked.connect(lambda: self._set_mode('highlight'))
        toolbar_layout.addWidget(self.highlight_btn)

        self.circle_btn = QPushButton("Circle")
        self.circle_btn.setCheckable(True)
        self.circle_btn.setStyleSheet(mode_style)
        self.circle_btn.clicked.connect(lambda: self._set_mode('circle'))
        toolbar_layout.addWidget(self.circle_btn)

        self.text_btn = QPushButton("Text")
        self.text_btn.setCheckable(True)
        self.text_btn.setStyleSheet(mode_style)
        self.text_btn.clicked.connect(lambda: self._set_mode('text'))
        toolbar_layout.addWidget(self.text_btn)

        self.mode_buttons = [self.highlight_btn, self.circle_btn, self.text_btn]

        toolbar_layout.addSpacing(15)

        # Brush size
        size_label = QLabel("Size:")
        size_label.setStyleSheet(f"color: {Theme.TEXT_DARK}; background: transparent;")
        toolbar_layout.addWidget(size_label)

        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(5, 50)
        self.size_slider.setValue(20)
        self.size_slider.setFixedWidth(100)
        self.size_slider.valueChanged.connect(self._on_size_changed)
        toolbar_layout.addWidget(self.size_slider)

        self.size_value = QLabel("20")
        self.size_value.setStyleSheet(f"color: {Theme.TEXT_DARK}; background: transparent;")
        toolbar_layout.addWidget(self.size_value)

        toolbar_layout.addSpacing(15)

        # Straight line checkbox
        self.straight_check = QCheckBox("Straight lines")
        self.straight_check.setStyleSheet(f"color: {Theme.TEXT_DARK}; background: transparent;")
        self.straight_check.stateChanged.connect(lambda s: setattr(self, 'straight_line', s == Qt.CheckState.Checked.value))
        toolbar_layout.addWidget(self.straight_check)

        toolbar_layout.addStretch()

        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.ERROR};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 10pt;
            }}
            QPushButton:hover {{
                background: #c0392b;
            }}
        """)
        cancel_btn.clicked.connect(self._cancel)
        toolbar_layout.addWidget(cancel_btn)

        # Save button
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.SUCCESS};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 10pt;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: #27ae60;
            }}
        """)
        save_btn.clicked.connect(self._save)
        toolbar_layout.addWidget(save_btn)

        layout.addWidget(toolbar)

        # Canvas
        self.canvas = QLabel()
        self.canvas.setFixedSize(self.display_size)
        self.canvas.setStyleSheet(f"background: white; border: 1px solid {Theme.BORDER};")
        self.canvas.setCursor(Qt.CursorShape.CrossCursor)
        self.canvas.setMouseTracking(True)
        layout.addWidget(self.canvas, alignment=Qt.AlignmentFlag.AlignCenter)

        # Install event filter for mouse events
        self.canvas.installEventFilter(self)

        self._update_canvas()

        # Select yellow by default
        self._set_color(self.COLORS['yellow'], 'yellow')

    def _set_color(self, color: QColor, name: str):
        self.current_color = color
        # Update button borders
        for n, btn in self.color_buttons.items():
            c = self.COLORS[n]
            opaque = QColor(c.red(), c.green(), c.blue())
            if n == name:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {opaque.name()};
                        border: 3px solid {Theme.ACCENT};
                        border-radius: 4px;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {opaque.name()};
                        border: 2px solid {Theme.TEXT_DARK};
                        border-radius: 4px;
                    }}
                    QPushButton:hover {{
                        border-width: 3px;
                    }}
                """)

    def _set_mode(self, mode: str):
        self.draw_mode = mode
        for btn in self.mode_buttons:
            btn.setChecked(False)
        if mode == 'highlight':
            self.highlight_btn.setChecked(True)
        elif mode == 'circle':
            self.circle_btn.setChecked(True)
        elif mode == 'text':
            self.text_btn.setChecked(True)

    def _on_size_changed(self, value: int):
        self.brush_size = value
        self.size_value.setText(str(value))

    def _update_canvas(self):
        """Composite all layers and display"""
        result = QPixmap(self.original_pixmap.size())
        painter = QPainter(result)
        painter.drawPixmap(0, 0, self.original_pixmap)
        painter.drawPixmap(0, 0, self.overlay_pixmap)
        painter.drawPixmap(0, 0, self.preview_pixmap)
        painter.end()

        # Scale for display
        scaled = result.scaled(self.display_size, Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
        self.canvas.setPixmap(scaled)

    def _canvas_to_image_pos(self, pos: QPoint) -> QPoint:
        """Convert canvas position to image position"""
        return QPoint(int(pos.x() / self.scale_factor), int(pos.y() / self.scale_factor))

    def eventFilter(self, obj, event):
        if obj == self.canvas:
            if event.type() == event.Type.MouseButtonPress:
                self._on_mouse_press(event)
                return True
            elif event.type() == event.Type.MouseMove:
                self._on_mouse_move(event)
                return True
            elif event.type() == event.Type.MouseButtonRelease:
                self._on_mouse_release(event)
                return True
        return super().eventFilter(obj, event)

    def _on_mouse_press(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = self._canvas_to_image_pos(event.pos())

            if self.draw_mode == 'text':
                # Show text input dialog
                text, ok = QInputDialog.getText(self, "Add Text", "Enter text:")
                if ok and text:
                    painter = QPainter(self.overlay_pixmap)
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

                    # Use opaque color for text
                    text_color = QColor(self.current_color.red(), self.current_color.green(),
                                       self.current_color.blue())
                    painter.setPen(text_color)

                    font = QFont("Segoe UI", self.brush_size)
                    font.setBold(True)
                    painter.setFont(font)
                    painter.drawText(pos, text)
                    painter.end()
                    self._update_canvas()
            else:
                self.drawing = True
                self.last_point = pos

                if self.draw_mode == 'circle':
                    self.circle_start = pos

    def _on_mouse_move(self, event: QMouseEvent):
        if self.drawing:
            pos = self._canvas_to_image_pos(event.pos())

            if self.draw_mode == 'highlight':
                painter = QPainter(self.overlay_pixmap)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(self.current_color)

                if self.straight_line:
                    # Constrain to horizontal or vertical
                    dx = abs(pos.x() - self.last_point.x())
                    dy = abs(pos.y() - self.last_point.y())
                    if dx > dy:
                        pos = QPoint(pos.x(), self.last_point.y())
                    else:
                        pos = QPoint(self.last_point.x(), pos.y())

                # Draw line of circles
                if self.last_point:
                    # Bresenham-style line
                    x0, y0 = self.last_point.x(), self.last_point.y()
                    x1, y1 = pos.x(), pos.y()

                    dx = abs(x1 - x0)
                    dy = abs(y1 - y0)
                    steps = max(dx, dy, 1)

                    for i in range(steps + 1):
                        t = i / steps if steps > 0 else 0
                        x = int(x0 + (x1 - x0) * t)
                        y = int(y0 + (y1 - y0) * t)
                        painter.drawEllipse(QPoint(x, y), self.brush_size // 2, self.brush_size // 2)

                painter.end()
                self.last_point = pos

            elif self.draw_mode == 'circle':
                # Clear preview and draw circle preview
                self.preview_pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(self.preview_pixmap)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)

                pen = QPen(self.current_color)
                pen.setWidth(max(2, self.brush_size // 3))
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)

                rect = QRect(self.circle_start, pos).normalized()
                painter.drawEllipse(rect)
                painter.end()

            self._update_canvas()

    def _on_mouse_release(self, event: QMouseEvent):
        if self.drawing:
            if self.draw_mode == 'circle':
                # Commit preview to overlay
                painter = QPainter(self.overlay_pixmap)
                painter.drawPixmap(0, 0, self.preview_pixmap)
                painter.end()
                self.preview_pixmap.fill(Qt.GlobalColor.transparent)

            self.drawing = False
            self.last_point = None
            self._update_canvas()

    def _save(self):
        # Composite final image
        result = QPixmap(self.original_pixmap.size())
        painter = QPainter(result)
        painter.drawPixmap(0, 0, self.original_pixmap)
        painter.drawPixmap(0, 0, self.overlay_pixmap)
        painter.end()

        self.editing_complete.emit(result)
        self.close()

    def _cancel(self):
        self.editing_cancelled.emit()
        self.close()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self._cancel()
        elif event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            self._save()


# ============================================================================
# SETTINGS DIALOG
# ============================================================================

class SettingsDialog(QDialog):
    """Settings configuration dialog"""

    def __init__(self, parent, config: dict):
        super().__init__(parent)
        self.config = config.copy()

        self.setWindowTitle("Settings")
        self.setFixedSize(400, 550)
        self.setStyleSheet(f"background: {Theme.BG_LIGHT};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Title
        title = QLabel("Settings")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        layout.addWidget(title)

        # Theme selector
        theme_frame = QFrame()
        theme_layout = QHBoxLayout(theme_frame)
        theme_layout.setContentsMargins(0, 0, 0, 0)

        theme_label = QLabel("Theme:")
        theme_label.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        theme_layout.addWidget(theme_label)

        self.theme_combo = QComboBox()
        for key, name in get_theme_names():
            self.theme_combo.addItem(name, key)
        # Set current theme
        current_theme = config.get('theme', 'solarized_dark')
        for i in range(self.theme_combo.count()):
            if self.theme_combo.itemData(i) == current_theme:
                self.theme_combo.setCurrentIndex(i)
                break
        theme_layout.addWidget(self.theme_combo)
        theme_layout.addStretch()

        layout.addWidget(theme_frame)

        layout.addSpacing(10)

        # Capture delay
        delay_frame = QFrame()
        delay_layout = QHBoxLayout(delay_frame)
        delay_layout.setContentsMargins(0, 0, 0, 0)

        delay_label = QLabel("Capture delay:")
        delay_label.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        delay_layout.addWidget(delay_label)

        self.delay_combo = QComboBox()
        self.delay_combo.addItems(["0 sec", "3 sec", "5 sec", "10 sec"])
        delay_val = config.get('delay', 0)
        delay_map = {0: 0, 3: 1, 5: 2, 10: 3}
        self.delay_combo.setCurrentIndex(delay_map.get(delay_val, 0))
        delay_layout.addWidget(self.delay_combo)
        delay_layout.addStretch()

        layout.addWidget(delay_frame)

        # Edit before save
        self.edit_check = QCheckBox("Edit before save")
        self.edit_check.setChecked(config.get('edit_before_save', True))
        self.edit_check.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        layout.addWidget(self.edit_check)

        # Silent capture
        self.silent_check = QCheckBox("Silent capture (don't show window)")
        self.silent_check.setChecked(config.get('silent_capture', False))
        self.silent_check.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        layout.addWidget(self.silent_check)

        # Pin to all desktops
        self.pin_check = QCheckBox("Pin to all virtual desktops")
        self.pin_check.setChecked(config.get('pin_to_all_desktops', False))
        self.pin_check.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        self.pin_check.setEnabled(PYVDA_AVAILABLE)
        if not PYVDA_AVAILABLE:
            self.pin_check.setToolTip("Install pyvda package for this feature")
        layout.addWidget(self.pin_check)

        # Thumbnail size
        thumb_frame = QFrame()
        thumb_layout = QHBoxLayout(thumb_frame)
        thumb_layout.setContentsMargins(0, 0, 0, 0)

        thumb_label = QLabel("Thumbnail size:")
        thumb_label.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        thumb_layout.addWidget(thumb_label)

        self.thumb_slider = QSlider(Qt.Orientation.Horizontal)
        self.thumb_slider.setRange(1, 10)
        self.thumb_slider.setValue(config.get('thumbnail_scale', 5))
        self.thumb_slider.setFixedWidth(150)
        thumb_layout.addWidget(self.thumb_slider)

        self.thumb_value = QLabel(str(config.get('thumbnail_scale', 5)))
        self.thumb_value.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        self.thumb_slider.valueChanged.connect(lambda v: self.thumb_value.setText(str(v)))
        thumb_layout.addWidget(self.thumb_value)
        thumb_layout.addStretch()

        layout.addWidget(thumb_frame)

        # Auto-send section
        layout.addSpacing(10)
        autosend_label = QLabel("Auto-send")
        autosend_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        autosend_label.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        layout.addWidget(autosend_label)

        self.autosend_check = QCheckBox("Auto-send to:")
        self.autosend_check.setChecked(config.get('auto_send_enabled', False))
        self.autosend_check.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        layout.addWidget(self.autosend_check)

        self.target_combo = QComboBox()
        targets = config.get('push_targets', [])
        for t in targets:
            self.target_combo.addItem(t.get('name', 'Unknown'))
        current_target = config.get('auto_send_target', '')
        idx = self.target_combo.findText(current_target)
        if idx >= 0:
            self.target_combo.setCurrentIndex(idx)
        layout.addWidget(self.target_combo)

        # Storage section
        layout.addSpacing(10)
        storage_label = QLabel("Storage")
        storage_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        storage_label.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        layout.addWidget(storage_label)

        # Disk limit
        limit_frame = QFrame()
        limit_layout = QHBoxLayout(limit_frame)
        limit_layout.setContentsMargins(0, 0, 0, 0)

        limit_label = QLabel("Disk limit (MB):")
        limit_label.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        limit_layout.addWidget(limit_label)

        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(100, 5000)
        self.limit_spin.setValue(config.get('disk_limit_mb', 500))
        self.limit_spin.setSingleStep(100)
        limit_layout.addWidget(self.limit_spin)
        limit_layout.addStretch()

        layout.addWidget(limit_frame)

        # Archive days
        archive_frame = QFrame()
        archive_layout = QHBoxLayout(archive_frame)
        archive_layout.setContentsMargins(0, 0, 0, 0)

        archive_label = QLabel("Auto-cleanup after (days):")
        archive_label.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        archive_layout.addWidget(archive_label)

        self.archive_spin = QSpinBox()
        self.archive_spin.setRange(7, 365)
        self.archive_spin.setValue(config.get('archive_days', 30))
        archive_layout.addWidget(self.archive_spin)
        archive_layout.addStretch()

        layout.addWidget(archive_frame)

        # Save location
        layout.addSpacing(10)
        loc_label = QLabel("Save location")
        loc_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        loc_label.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        layout.addWidget(loc_label)

        self.path_label = QLabel(str(config.get('save_dir', SAVE_DIR)))
        self.path_label.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 9pt;")
        self.path_label.setWordWrap(True)
        layout.addWidget(self.path_label)

        path_btns = QHBoxLayout()
        change_btn = QPushButton("Change...")
        change_btn.clicked.connect(self._change_path)
        path_btns.addWidget(change_btn)

        open_btn = QPushButton("Open Folder")
        open_btn.clicked.connect(self._open_folder)
        path_btns.addWidget(open_btn)
        path_btns.addStretch()

        layout.addLayout(path_btns)

        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_CONTENT};
                color: {Theme.TEXT_DARK};
                border: 1px solid {Theme.BORDER};
                border-radius: 4px;
                padding: 8px 20px;
            }}
            QPushButton:hover {{
                background: {Theme.BORDER};
            }}
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.ACCENT};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 20px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: #2AA198;
            }}
        """)
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _change_path(self):
        path = QFileDialog.getExistingDirectory(self, "Select Save Folder", str(self.config.get('save_dir', SAVE_DIR)))
        if path:
            self.config['save_dir'] = path
            self.path_label.setText(path)

    def _open_folder(self):
        path = self.config.get('save_dir', SAVE_DIR)
        os.startfile(str(path))

    def _save(self):
        # Update config
        self.config['theme'] = self.theme_combo.currentData()
        delay_text = self.delay_combo.currentText()
        self.config['delay'] = int(delay_text.split()[0])
        self.config['edit_before_save'] = self.edit_check.isChecked()
        self.config['silent_capture'] = self.silent_check.isChecked()
        self.config['pin_to_all_desktops'] = self.pin_check.isChecked()
        self.config['thumbnail_scale'] = self.thumb_slider.value()
        self.config['auto_send_enabled'] = self.autosend_check.isChecked()
        self.config['auto_send_target'] = self.target_combo.currentText()
        self.config['disk_limit_mb'] = self.limit_spin.value()
        self.config['archive_days'] = self.archive_spin.value()

        self.accept()

    def get_config(self) -> dict:
        return self.config


# ============================================================================
# MAIN WINDOW
# ============================================================================

class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()

        # State
        self.current_folder: Optional[str] = None
        self.capture_in_progress = False
        self.session_count = 0

        # Load config
        self.config = self._load_config()
        self.save_dir = Path(self.config.get('save_dir', SAVE_DIR))
        self.save_dir.mkdir(parents=True, exist_ok=True)

        # Setup UI
        self._setup_ui()

        # Register hotkeys
        self._register_hotkeys()

        # Initial gallery refresh
        QTimer.singleShot(100, self._refresh_gallery)

        # Pin to all virtual desktops after window is shown
        if self.config.get('pin_to_all_desktops', False):
            QTimer.singleShot(500, self._pin_to_all_desktops)

    def _load_config(self) -> dict:
        """Load configuration from JSON file"""
        default_config = {
            'save_dir': str(SAVE_DIR),
            'theme': 'solarized_dark',
            'delay': 0,
            'edit_before_save': True,
            'silent_capture': False,
            'pin_to_all_desktops': False,
            'thumbnail_scale': 5,
            'auto_send_enabled': False,
            'auto_send_target': '',
            'disk_limit_mb': 500,
            'archive_days': 30,
            'push_targets': [
                {'name': 'VSCode Claude', 'title_pattern': 'claude code|visual studio code', 'enabled': True},
                {'name': 'WhatsApp', 'title_pattern': 'WhatsApp', 'enabled': True},
                {'name': 'Discord', 'title_pattern': 'Discord', 'enabled': True},
                {'name': 'Slack', 'title_pattern': 'Slack', 'enabled': True},
                {'name': 'Teams', 'title_pattern': 'Microsoft Teams', 'enabled': True},
            ]
        }

        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r') as f:
                    loaded = json.load(f)
                    default_config.update(loaded)
            except Exception as e:
                logging.error(f"Failed to load config: {e}")

        # Apply loaded theme
        set_active_theme(default_config.get('theme', 'solarized_dark'))

        return default_config

    def _save_config(self):
        """Save configuration to JSON file"""
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logging.error(f"Failed to save config: {e}")

    def _setup_ui(self):
        """Setup the main UI"""
        # Frameless window
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setGeometry(100, 100, 900, 650)
        self.setStyleSheet(generate_stylesheet())

        # Set window icon
        logo_path = Path(__file__).parent / "logo.png"
        if logo_path.exists():
            self.setWindowIcon(QIcon(str(logo_path)))

        # Main container
        container = QWidget()
        container.setStyleSheet(f"background: {Theme.BG_GALLERY};")
        self.setCentralWidget(container)

        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Title bar
        self.title_bar = CustomTitleBar(self)
        main_layout.addWidget(self.title_bar)

        # Content area with splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)

        # Sidebar
        sidebar = self._create_sidebar()
        splitter.addWidget(sidebar)

        # Gallery area
        gallery_container = self._create_gallery()
        splitter.addWidget(gallery_container)

        splitter.setSizes([200, 700])
        main_layout.addWidget(splitter)

        # Status bar
        self.status_bar = QLabel("Ready")
        self.status_bar.setObjectName("statusBar")
        self.status_bar.setFixedHeight(30)
        main_layout.addWidget(self.status_bar)

    def _create_sidebar(self) -> QWidget:
        """Create the sidebar with buttons"""
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(200)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Logo
        logo_path = Path(__file__).parent / "logo.png"
        if logo_path.exists():
            logo_label = QLabel()
            logo_pixmap = QPixmap(str(logo_path))
            scaled = logo_pixmap.scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(scaled)
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logo_label.setStyleSheet("background: transparent;")
            layout.addWidget(logo_label)
            layout.addSpacing(10)

        # Capture buttons
        btn_style = f"""
            QPushButton {{
                background: {Theme.BUTTON_BG};
                color: {Theme.BUTTON_TEXT};
                border: none;
                border-radius: 6px;
                padding: 10px 15px;
                text-align: left;
                font-size: 10pt;
            }}
            QPushButton:hover {{
                background: {Theme.BUTTON_HOVER};
            }}
            QPushButton:pressed {{
                background: {Theme.ACCENT};
            }}
        """

        region_btn = QPushButton("📷 Region (Ctrl+Shift+R)")
        region_btn.setStyleSheet(btn_style)
        region_btn.clicked.connect(self._start_region_capture)
        layout.addWidget(region_btn)

        screen_btn = QPushButton("🖥️ Screen (Ctrl+Shift+S)")
        screen_btn.setStyleSheet(btn_style)
        screen_btn.clicked.connect(self._capture_fullscreen)
        layout.addWidget(screen_btn)

        window_btn = QPushButton("🪟 Window (Ctrl+Shift+W)")
        window_btn.setStyleSheet(btn_style)
        window_btn.clicked.connect(self._start_window_capture)
        layout.addWidget(window_btn)

        layout.addSpacing(15)

        # Import buttons
        import_btn = QPushButton("📁 Import from File")
        import_btn.setStyleSheet(btn_style)
        import_btn.clicked.connect(self._import_image)
        layout.addWidget(import_btn)

        paste_btn = QPushButton("📋 Paste from Clipboard")
        paste_btn.setStyleSheet(btn_style)
        paste_btn.clicked.connect(self._paste_from_clipboard)
        layout.addWidget(paste_btn)

        layout.addStretch()

        # Settings button
        settings_btn = QPushButton("⚙️ Settings")
        settings_btn.setStyleSheet(btn_style)
        settings_btn.clicked.connect(self._show_settings)
        layout.addWidget(settings_btn)

        # Disk usage
        self.disk_label = QLabel("Calculating...")
        self.disk_label.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 9pt;")
        layout.addWidget(self.disk_label)

        # Session counter
        self.session_label = QLabel("Screenshots: 0")
        self.session_label.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 9pt;")
        layout.addWidget(self.session_label)

        # About button
        about_btn = QPushButton("About")
        about_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {Theme.TEXT_MUTED};
                border: none;
                text-align: left;
                padding: 5px;
                font-size: 9pt;
            }}
            QPushButton:hover {{
                color: {Theme.TEXT_LIGHT};
            }}
        """)
        about_btn.clicked.connect(self._show_about)
        layout.addWidget(about_btn)

        return sidebar

    def _create_gallery(self) -> QWidget:
        """Create the gallery area with folder bar and thumbnails"""
        container = QFrame()
        container.setObjectName("gallery")

        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Folder bar
        self.folder_bar = QFrame()
        self.folder_bar.setObjectName("folderBar")
        self.folder_bar.setFixedHeight(70)

        self.folder_layout = QHBoxLayout(self.folder_bar)
        self.folder_layout.setContentsMargins(10, 10, 10, 10)
        self.folder_layout.setSpacing(8)

        layout.addWidget(self.folder_bar)

        # Gallery scroll area
        self.gallery_scroll = QScrollArea()
        self.gallery_scroll.setWidgetResizable(True)
        self.gallery_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.gallery_widget = QWidget()
        self.gallery_widget.setStyleSheet(f"background: {Theme.BG_DARK};")
        self.gallery_grid = QGridLayout(self.gallery_widget)
        self.gallery_grid.setContentsMargins(15, 15, 15, 15)
        self.gallery_grid.setSpacing(10)
        self.gallery_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self.gallery_scroll.setWidget(self.gallery_widget)
        layout.addWidget(self.gallery_scroll)

        return container

    def _refresh_folder_bar(self):
        """Refresh the folder buttons"""
        # Clear existing
        while self.folder_layout.count():
            item = self.folder_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # "All" button
        all_btn = FolderButton(None, self.save_dir, self.current_folder is None)
        all_btn.clicked.connect(self._select_folder)
        self.folder_layout.addWidget(all_btn)

        # Folder buttons
        folders = self._get_folders()
        for folder in folders:
            btn = FolderButton(folder, self.save_dir, self.current_folder == folder)
            btn.clicked.connect(self._select_folder)
            btn.context_menu_requested.connect(self._folder_context_menu)
            btn.file_dropped.connect(self._move_to_folder)
            self.folder_layout.addWidget(btn)

        # Add folder button
        add_btn = QPushButton("+")
        add_btn.setFixedSize(40, 50)
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BUTTON_BG};
                color: {Theme.ACCENT};
                border: 2px dashed {Theme.BUTTON_HOVER};
                border-radius: 6px;
                font-size: 20px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                border-color: {Theme.ACCENT};
                background: {Theme.BUTTON_HOVER};
            }}
        """)
        add_btn.clicked.connect(self._create_folder)
        self.folder_layout.addWidget(add_btn)

        self.folder_layout.addStretch()

    def _get_folders(self) -> List[str]:
        """Get list of subfolders"""
        folders = []
        if self.save_dir.exists():
            for item in self.save_dir.iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    folders.append(item.name)
        return sorted(folders)

    def _select_folder(self, folder_name: Optional[str]):
        """Select a folder to filter gallery"""
        self.current_folder = folder_name
        self._refresh_folder_bar()
        self._refresh_gallery()

    def _refresh_gallery(self):
        """Refresh the thumbnail gallery"""
        # Clear existing
        while self.gallery_grid.count():
            item = self.gallery_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Get images
        if self.current_folder:
            folder_path = self.save_dir / self.current_folder
        else:
            folder_path = self.save_dir

        images = []
        if folder_path.exists():
            # Get from folder and subfolders if "All"
            if self.current_folder is None:
                for item in folder_path.rglob("*.png"):
                    if item.is_file():
                        images.append(item)
            else:
                for item in folder_path.glob("*.png"):
                    if item.is_file():
                        images.append(item)

        # Sort by modification time
        images.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        # Calculate thumbnail size
        scale = self.config.get('thumbnail_scale', 5)
        thumb_size = QSize(80 + scale * 15, 60 + scale * 12)

        # Calculate columns
        gallery_width = self.gallery_scroll.width() - 50
        cols = max(1, gallery_width // (thumb_size.width() + 20))

        # Add thumbnails
        for i, img_path in enumerate(images):
            thumb = ThumbnailWidget(img_path, thumb_size)
            thumb.clicked.connect(self._on_thumbnail_click)
            thumb.double_clicked.connect(self._open_image)
            thumb.context_menu_requested.connect(self._thumbnail_context_menu)

            row = i // cols
            col = i % cols
            self.gallery_grid.addWidget(thumb, row, col)

        # Update folder bar
        self._refresh_folder_bar()

        # Update disk usage
        self._update_disk_usage()

    def _on_thumbnail_click(self, filepath: Path):
        """Handle single click on thumbnail"""
        self._open_image(filepath)

    def _open_image(self, filepath: Path):
        """Open image in system viewer"""
        try:
            os.startfile(str(filepath))
        except Exception as e:
            logging.error(f"Failed to open image: {e}")

    def _thumbnail_context_menu(self, filepath: Path, pos: QPoint):
        """Show context menu for thumbnail"""
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background: {Theme.BG_LIGHT};
                border: 1px solid {Theme.BORDER};
                border-radius: 4px;
                padding: 5px;
            }}
            QMenu::item {{
                padding: 8px 20px;
                color: {Theme.TEXT_DARK};
            }}
            QMenu::item:selected {{
                background: {Theme.ACCENT};
                color: white;
            }}
        """)

        open_action = menu.addAction("Open")
        open_action.triggered.connect(lambda: self._open_image(filepath))

        edit_action = menu.addAction("Edit")
        edit_action.triggered.connect(lambda: self._edit_image(filepath))

        copy_action = menu.addAction("Copy to Clipboard")
        copy_action.triggered.connect(lambda: self._copy_to_clipboard(filepath))

        menu.addSeparator()

        # Send to submenu
        send_menu = menu.addMenu("Send to...")
        targets = self.config.get('push_targets', [])
        for target in targets:
            if target.get('enabled', True):
                action = send_menu.addAction(target['name'])
                action.triggered.connect(
                    lambda checked, t=target['name'], p=filepath: self._send_to_target(t, p)
                )

        # Move to submenu
        move_menu = menu.addMenu("Move to...")
        folders = self._get_folders()

        if self.current_folder:
            root_action = move_menu.addAction("Root folder")
            root_action.triggered.connect(lambda: self._move_file(filepath, None))

        for folder in folders:
            if folder != self.current_folder:
                action = move_menu.addAction(folder)
                action.triggered.connect(lambda checked, f=folder: self._move_file(filepath, f))

        menu.addSeparator()

        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(lambda: self._delete_image(filepath))

        menu.exec(pos)

    def _folder_context_menu(self, folder_name: str, pos: QPoint):
        """Show context menu for folder"""
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background: {Theme.BG_LIGHT};
                border: 1px solid {Theme.BORDER};
                border-radius: 4px;
                padding: 5px;
            }}
            QMenu::item {{
                padding: 8px 20px;
                color: {Theme.TEXT_DARK};
            }}
            QMenu::item:selected {{
                background: {Theme.ACCENT};
                color: white;
            }}
        """)

        rename_action = menu.addAction("Rename")
        rename_action.triggered.connect(lambda: self._rename_folder(folder_name))

        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(lambda: self._delete_folder(folder_name))

        menu.exec(pos)

    def _create_folder(self):
        """Create a new folder"""
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if ok and name:
            folder_path = self.save_dir / name
            try:
                folder_path.mkdir(exist_ok=True)
                self._refresh_folder_bar()
                self._set_status(f"Created folder: {name}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to create folder: {e}")

    def _rename_folder(self, folder_name: str):
        """Rename a folder"""
        new_name, ok = QInputDialog.getText(self, "Rename Folder", "New name:", text=folder_name)
        if ok and new_name and new_name != folder_name:
            old_path = self.save_dir / folder_name
            new_path = self.save_dir / new_name
            try:
                shutil.move(str(old_path), str(new_path))
                if self.current_folder == folder_name:
                    self.current_folder = new_name
                self._refresh_gallery()
                self._set_status(f"Renamed folder to: {new_name}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to rename folder: {e}")

    def _delete_folder(self, folder_name: str):
        """Delete a folder"""
        reply = QMessageBox.question(
            self, "Delete Folder",
            f"Delete folder '{folder_name}' and all its contents?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            folder_path = self.save_dir / folder_name
            try:
                shutil.rmtree(str(folder_path))
                if self.current_folder == folder_name:
                    self.current_folder = None
                self._refresh_gallery()
                self._set_status(f"Deleted folder: {folder_name}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to delete folder: {e}")

    def _move_file(self, filepath: Path, target_folder: Optional[str]):
        """Move file to target folder"""
        if target_folder:
            target = self.save_dir / target_folder / filepath.name
        else:
            target = self.save_dir / filepath.name

        try:
            shutil.move(str(filepath), str(target))
            self._refresh_gallery()
            self._set_status(f"Moved to: {target_folder or 'root'}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to move file: {e}")

    def _move_to_folder(self, folder_name: Optional[str], source_path: Path):
        """Handle file drop on folder"""
        self._move_file(source_path, folder_name)

    def _delete_image(self, filepath: Path):
        """Delete an image"""
        reply = QMessageBox.question(
            self, "Delete Screenshot",
            f"Delete {filepath.name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                filepath.unlink()
                self._refresh_gallery()
                self._set_status("Screenshot deleted")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to delete: {e}")

    def _edit_image(self, filepath: Path):
        """Open image in editor"""
        pixmap = QPixmap(str(filepath))
        if pixmap.isNull():
            QMessageBox.warning(self, "Error", "Failed to load image")
            return

        self.editor = ScreenshotEditor(pixmap)
        self.editor.editing_complete.connect(lambda p: self._save_edited(p, filepath))
        self.editor.show()

    def _save_edited(self, pixmap: QPixmap, filepath: Path):
        """Save edited image back to file"""
        try:
            pixmap.save(str(filepath), "PNG")
            self._refresh_gallery()
            self._set_status("Image saved")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save: {e}")

    def _copy_to_clipboard(self, filepath: Path):
        """Copy image to clipboard"""
        try:
            img = Image.open(str(filepath))
            self._copy_pil_to_clipboard(img)
            self._set_status("Copied to clipboard")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to copy: {e}")

    def _copy_pil_to_clipboard(self, img: Image.Image):
        """Copy PIL image to Windows clipboard"""
        output = BytesIO()
        img.convert("RGB").save(output, "BMP")
        data = output.getvalue()[14:]  # Remove BMP header
        output.close()

        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
        win32clipboard.CloseClipboard()

    def _copy_pixmap_to_clipboard(self, pixmap: QPixmap):
        """Copy QPixmap directly to Windows clipboard (faster than going through disk)"""
        # Convert QPixmap to QImage
        image = pixmap.toImage()
        if image.format() != QImage.Format.Format_RGB32:
            image = image.convertToFormat(QImage.Format.Format_RGB32)

        # Get raw bytes
        width = image.width()
        height = image.height()
        ptr = image.bits()
        ptr.setsize(height * width * 4)

        # Create BMP data (DIB format for clipboard)
        # DIB is bottom-up, so we need to flip
        output = BytesIO()
        for y in range(height - 1, -1, -1):
            row_start = y * width * 4
            row_end = row_start + width * 4
            output.write(bytes(ptr[row_start:row_end]))

        data = output.getvalue()
        output.close()

        # Create BITMAPINFOHEADER
        import struct
        header = struct.pack('<IiiHHIIiiII',
            40,           # biSize
            width,        # biWidth
            height,       # biHeight
            1,            # biPlanes
            32,           # biBitCount
            0,            # biCompression (BI_RGB)
            len(data),    # biSizeImage
            0,            # biXPelsPerMeter
            0,            # biYPelsPerMeter
            0,            # biClrUsed
            0             # biClrImportant
        )

        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, header + data)
        win32clipboard.CloseClipboard()

    def _update_disk_usage(self):
        """Update disk usage display"""
        total = 0
        if self.save_dir.exists():
            for f in self.save_dir.rglob("*"):
                if f.is_file():
                    total += f.stat().st_size

        mb = total / (1024 * 1024)
        limit = self.config.get('disk_limit_mb', 500)
        self.disk_label.setText(f"Storage: {mb:.1f} / {limit} MB")

    def _set_status(self, message: str):
        """Update status bar"""
        self.status_bar.setText(message)

    def _register_hotkeys(self):
        """Register global hotkeys"""
        try:
            keyboard.add_hotkey('ctrl+shift+s', self._hotkey_fullscreen)
            keyboard.add_hotkey('ctrl+shift+r', self._hotkey_region)
            keyboard.add_hotkey('ctrl+shift+w', self._hotkey_window)
        except Exception as e:
            logging.error(f"Failed to register hotkeys: {e}")

    def _hotkey_fullscreen(self):
        """Hotkey callback for fullscreen capture"""
        QTimer.singleShot(0, self._capture_fullscreen)

    def _hotkey_region(self):
        """Hotkey callback for region capture"""
        QTimer.singleShot(0, self._start_region_capture)

    def _hotkey_window(self):
        """Hotkey callback for window capture"""
        QTimer.singleShot(0, self._start_window_capture)

    def _start_region_capture(self):
        """Start region capture"""
        if self.capture_in_progress:
            return
        self.capture_in_progress = True

        delay = self.config.get('delay', 0)
        if delay > 0:
            self.countdown = DelayCountdown(delay)
            self.countdown.countdown_complete.connect(self._do_region_capture)
            self.countdown.countdown_cancelled.connect(self._capture_cancelled)
            self.countdown.show()
        else:
            # Small delay to let window hide
            if not self.config.get('silent_capture', False):
                self.hide()
            QTimer.singleShot(50, self._do_region_capture)

    def _do_region_capture(self):
        """Execute region capture"""
        self.region_selector = RegionSelector()
        self.region_selector.region_selected.connect(self._on_region_captured)
        self.region_selector.cancelled.connect(self._capture_cancelled)
        self.region_selector.show()

    def _on_region_captured(self, rect: QRect, pixmap: QPixmap):
        """Handle captured region"""
        self._process_capture(pixmap)

    def _capture_fullscreen(self):
        """Capture full screen"""
        if self.capture_in_progress:
            return
        self.capture_in_progress = True

        delay = self.config.get('delay', 0)
        if delay > 0:
            self.countdown = DelayCountdown(delay)
            self.countdown.countdown_complete.connect(self._do_fullscreen_capture)
            self.countdown.countdown_cancelled.connect(self._capture_cancelled)
            self.countdown.show()
        else:
            if not self.config.get('silent_capture', False):
                self.hide()
            QTimer.singleShot(50, self._do_fullscreen_capture)

    def _do_fullscreen_capture(self):
        """Execute fullscreen capture"""
        with mss.mss() as sct:
            monitor = sct.monitors[0]
            screenshot = sct.grab(monitor)
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

            # Convert to QPixmap
            data = img.tobytes("raw", "RGB")
            qimage = QImage(data, img.width, img.height, img.width * 3, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qimage)

            self._process_capture(pixmap)

    def _start_window_capture(self):
        """Start window capture"""
        if self.capture_in_progress:
            return
        self.capture_in_progress = True

        if not self.config.get('silent_capture', False):
            self.hide()

        QTimer.singleShot(50, self._do_window_capture)

    def _do_window_capture(self):
        """Execute window capture selection"""
        self.window_selector = WindowSelector()
        self.window_selector.window_selected.connect(self._capture_window)
        self.window_selector.cancelled.connect(self._capture_cancelled)
        self.window_selector.show()

    def _capture_window(self, hwnd: int):
        """Capture specific window"""
        try:
            # Get window rect
            rect = win32gui.GetWindowRect(hwnd)
            x, y, x2, y2 = rect
            w = x2 - x
            h = y2 - y

            # Capture using mss
            with mss.mss() as sct:
                monitor = {"left": x, "top": y, "width": w, "height": h}
                screenshot = sct.grab(monitor)
                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

                # Convert to QPixmap
                data = img.tobytes("raw", "RGB")
                qimage = QImage(data, img.width, img.height, img.width * 3, QImage.Format.Format_RGB888)
                pixmap = QPixmap.fromImage(qimage)

                self._process_capture(pixmap)
        except Exception as e:
            logging.error(f"Window capture failed: {e}")
            self._capture_cancelled()

    def _capture_cancelled(self):
        """Handle capture cancellation"""
        self.capture_in_progress = False
        if not self.config.get('silent_capture', False):
            self.show()
        self._set_status("Capture cancelled")

    def _process_capture(self, pixmap: QPixmap):
        """Process captured screenshot"""
        if self.config.get('edit_before_save', True):
            self.editor = ScreenshotEditor(pixmap)
            self.editor.editing_complete.connect(self._save_screenshot)
            self.editor.editing_cancelled.connect(self._capture_cancelled)
            self.editor.show()
        else:
            self._save_screenshot(pixmap)

    def _save_screenshot(self, pixmap: QPixmap):
        """Save screenshot to disk"""
        self.capture_in_progress = False

        # Copy to clipboard FIRST (instant feedback)
        self._copy_pixmap_to_clipboard(pixmap)

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"

        # Determine save path
        if self.current_folder:
            save_path = self.save_dir / self.current_folder / filename
            save_path.parent.mkdir(exist_ok=True)
        else:
            save_path = self.save_dir / filename

        # Save to disk
        pixmap.save(str(save_path), "PNG")

        # Update state
        self.session_count += 1
        self.session_label.setText(f"Screenshots: {self.session_count}")

        # Show notification immediately
        self.toast = ToastNotification(pixmap, filename)
        self._set_status(f"Saved: {filename}")

        # Show window if not silent
        if not self.config.get('silent_capture', False):
            self.show()

        # Defer gallery refresh (non-blocking)
        QTimer.singleShot(100, self._refresh_gallery)

        # Auto-send if enabled
        if self.config.get('auto_send_enabled', False):
            target = self.config.get('auto_send_target', '')
            if target:
                QTimer.singleShot(500, lambda: self._send_to_target(target))

    def _send_to_target(self, target_name: str, filepath: Path = None):
        """Send screenshot to target application"""
        targets = self.config.get('push_targets', [])
        target = next((t for t in targets if t.get('name') == target_name), None)

        if not target:
            return

        # Copy image to clipboard first if filepath provided
        if filepath:
            try:
                img = Image.open(str(filepath))
                self._copy_pil_to_clipboard(img)
            except Exception as e:
                self._set_status(f"Failed to copy image: {e}")
                return

        pattern = target.get('title_pattern', '').lower()

        # Find window
        def find_window(hwnd, results):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd).lower()
                for p in pattern.split('|'):
                    if p in title:
                        results.append(hwnd)
            return True

        results = []
        win32gui.EnumWindows(find_window, results)

        if not results:
            self._set_status(f"'{target_name}' window not found")
            return

        hwnd = results[0]
        try:
            # Restore if minimized
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

            # Activate window
            win32gui.SetForegroundWindow(hwnd)
            QTimer.singleShot(300, lambda: pyautogui.hotkey('ctrl', 'v'))
            self._set_status(f"Sent to {target_name}")
        except Exception as e:
            logging.error(f"Failed to send to target: {e}")
            self._set_status(f"Send to {target_name} failed")

    def _import_image(self):
        """Import image from file"""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Import Image",
            str(Path.home() / "Pictures"),
            "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if filepath:
            try:
                img = Image.open(filepath)

                # Convert to QPixmap
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                data = img.tobytes("raw", "RGB")
                qimage = QImage(data, img.width, img.height, img.width * 3, QImage.Format.Format_RGB888)
                pixmap = QPixmap.fromImage(qimage)

                self._process_capture(pixmap)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to import: {e}")

    def _paste_from_clipboard(self):
        """Paste image from clipboard"""
        try:
            img = ImageGrab.grabclipboard()
            if img:
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                data = img.tobytes("raw", "RGB")
                qimage = QImage(data, img.width, img.height, img.width * 3, QImage.Format.Format_RGB888)
                pixmap = QPixmap.fromImage(qimage)

                self._process_capture(pixmap)
            else:
                QMessageBox.information(self, "Clipboard", "No image in clipboard")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to paste: {e}")

    def _show_settings(self):
        """Show settings dialog"""
        old_theme = self.config.get('theme', 'solarized_dark')
        old_pin = self.config.get('pin_to_all_desktops', False)
        dialog = SettingsDialog(self, self.config)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.config = dialog.get_config()
            self._save_config()

            # Check if theme changed
            new_theme = self.config.get('theme', 'solarized_dark')
            if new_theme != old_theme:
                self._apply_theme(new_theme)

            # Check if pin setting changed
            new_pin = self.config.get('pin_to_all_desktops', False)
            if new_pin != old_pin:
                if new_pin:
                    self._pin_to_all_desktops()
                else:
                    self._unpin_from_all_desktops()

            self._refresh_gallery()
            self._set_status("Settings saved")

    def _apply_theme(self, theme_key: str):
        """Apply a new theme to the application"""
        set_active_theme(theme_key)

        # Update main stylesheet
        self.setStyleSheet(generate_stylesheet())

        # Update container background
        container = self.centralWidget()
        if container:
            container.setStyleSheet(f"background: {Theme.BG_GALLERY};")

        # Update gallery widget background
        if hasattr(self, 'gallery_widget'):
            self.gallery_widget.setStyleSheet(f"background: {Theme.BG_GALLERY};")

        # Rebuild sidebar and title bar (they have inline styles)
        self._rebuild_sidebar()
        self._rebuild_title_bar()

    def _rebuild_sidebar(self):
        """Rebuild sidebar with current theme"""
        # Find the splitter
        splitter = None
        for child in self.centralWidget().children():
            if isinstance(child, QSplitter):
                splitter = child
                break

        if splitter and splitter.count() > 0:
            old_sidebar = splitter.widget(0)
            new_sidebar = self._create_sidebar()
            splitter.replaceWidget(0, new_sidebar)
            old_sidebar.deleteLater()

    def _rebuild_title_bar(self):
        """Rebuild title bar with current theme"""
        main_layout = self.centralWidget().layout()
        if main_layout and main_layout.count() > 0:
            old_title_bar = main_layout.itemAt(0).widget()
            if isinstance(old_title_bar, CustomTitleBar):
                new_title_bar = CustomTitleBar(self)
                main_layout.replaceWidget(old_title_bar, new_title_bar)
                self.title_bar = new_title_bar
                old_title_bar.deleteLater()

    def _show_about(self):
        """Show about dialog"""
        about = QDialog(self)
        about.setWindowTitle("About")
        about.setFixedSize(300, 250)
        about.setStyleSheet(f"background: {Theme.BG_LIGHT};")

        layout = QVBoxLayout(about)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Logo
        logo_path = Path(__file__).parent / "logo.png"
        if logo_path.exists():
            logo = QLabel()
            pixmap = QPixmap(str(logo_path))
            scaled = pixmap.scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio)
            logo.setPixmap(scaled)
            logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(logo)

        # Title
        title = QLabel(APP_NAME)
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Version
        version = QLabel(f"Version {APP_VERSION}")
        version.setStyleSheet(f"color: {Theme.TEXT_MUTED};")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)

        # Description
        desc = QLabel("A modern screenshot utility\nfor Windows")
        desc.setStyleSheet(f"color: {Theme.TEXT_GRAY};")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        layout.addStretch()

        # Close button
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.ACCENT};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 20px;
            }}
            QPushButton:hover {{
                background: #2AA198;
            }}
        """)
        close_btn.clicked.connect(about.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        about.exec()

    def resizeEvent(self, event):
        """Handle window resize"""
        super().resizeEvent(event)
        # Refresh gallery to adjust columns
        QTimer.singleShot(100, self._refresh_gallery)

    def _pin_to_all_desktops(self):
        """Pin the window to appear on all virtual desktops"""
        if not PYVDA_AVAILABLE:
            self._set_status("Install pyvda for virtual desktop pinning")
            return False

        try:
            hwnd = int(self.winId())
            view = AppView(hwnd)
            view.pin()
            self._set_status("Pinned to all virtual desktops")
            return True
        except Exception as e:
            logging.error(f"Pin failed: {e}")
            self._set_status("Pin failed - use Win+Tab to pin manually")
            return False

    def _unpin_from_all_desktops(self):
        """Unpin the window from all virtual desktops"""
        if not PYVDA_AVAILABLE:
            return False

        try:
            hwnd = int(self.winId())
            view = AppView(hwnd)
            view.unpin()
            self._set_status("Unpinned from all desktops")
            return True
        except Exception as e:
            logging.error(f"Unpin failed: {e}")
            return False

    def closeEvent(self, event):
        """Handle window close"""
        # Unregister hotkeys
        try:
            keyboard.remove_all_hotkeys()
        except:
            pass

        # Save config
        self._save_config()

        event.accept()


# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    # High DPI support
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)

    # Set app icon
    logo_path = Path(__file__).parent / "logo.png"
    if logo_path.exists():
        app.setWindowIcon(QIcon(str(logo_path)))

    try:
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        logging.error(f"Application error: {e}\n{traceback.format_exc()}")
        raise


if __name__ == "__main__":
    main()
