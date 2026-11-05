"""Voice test: say a phrase and see, side by side, what each speech engine writes from YOUR voice
and how long each takes. Nothing is saved. Not part of Otterly; a one-off comparison tool.

  live     - what Otterly's voice typing types today (FastConformer 480 ms + punctuation model)
  v2 / v3  - NVIDIA Parakeet TDT 0.6B, English (v2) and 25 European languages (v3), re-hearing the
             whole phrase at once
  whisper  - the Whisper model behind the editor's voice note box
"""
import os
import sys
import time
import html
import threading
import importlib.util
import importlib.machinery

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "screenshot_tool_pyqt.py")
spec = importlib.util.spec_from_loader("otterly_voice_test", importlib.machinery.SourceFileLoader("otterly_voice_test", APP))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

import numpy as np
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
                             QTextBrowser, QProgressBar)
from PyQt6.QtCore import QThread, pyqtSignal, QTimer, Qt

PARAKEET = {
    "v2": "sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8",
    "v3": "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8",
}
READY = threading.Event()          # set once every model is loaded, so timings never include loading
HEAR_LOCK = threading.Lock()       # one phrase at a time, so the engines do not slow each other down
ENGINES = [("live", "Otterly now (live)"), ("v2", "Parakeet v2 (English)"),
           ("v3", "Parakeet v3 (also Spanish)"), ("whisper", "Whisper (voice note box)")]


class Models:
    lock = threading.Lock()
    parakeet = {}

    @classmethod
    def get_parakeet(cls, key):
        with cls.lock:
            if key not in cls.parakeet:
                import sherpa_onnx
                d = os.path.join(str(m.LIVE_DIR), PARAKEET[key])
                cls.parakeet[key] = sherpa_onnx.OfflineRecognizer.from_transducer(
                    encoder=os.path.join(d, "encoder.int8.onnx"), decoder=os.path.join(d, "decoder.int8.onnx"),
                    joiner=os.path.join(d, "joiner.int8.onnx"), tokens=os.path.join(d, "tokens.txt"),
                    num_threads=4, model_type="nemo_transducer", decoding_method="greedy_search")
            return cls.parakeet[key]


def run_live(audio):
    """The recording through Otterly's live engine exactly as voice typing does it: 100 ms pieces,
    a phrase typed at each pause, punctuated on from the phrases before."""
    asr, punct = m._LiveModels.load()
    s = asr.create_stream()
    ph = m._LivePhrases(punct)
    out = ""
    full = np.concatenate([audio, np.zeros(m.WHISPER_RATE, dtype=np.float32)])
    for i in range(0, len(full), 1600):
        s.accept_waveform(m.WHISPER_RATE, full[i:i + 1600])
        while asr.is_ready(s):
            asr.decode_stream(s)
        if asr.is_endpoint(s):
            out += ph.take(asr.get_result(s).strip())
            asr.reset(s)
    s.input_finished()
    while asr.is_ready(s):
        asr.decode_stream(s)
    out += ph.take(asr.get_result(s).strip())
    return out + ph.ending()


def run_parakeet(key, audio):
    r = Models.get_parakeet(key)
    st = r.create_stream()
    st.accept_waveform(m.WHISPER_RATE, audio)
    r.decode_stream(st)
    return st.result.text.strip()


class Warmup(QThread):
    status = pyqtSignal(str)

    def run(self):
        steps = [("the live model", lambda: m._LiveModels.load()),
                 ("Parakeet v2", lambda: Models.get_parakeet("v2")),
                 ("Parakeet v3", lambda: Models.get_parakeet("v3")),
                 ("Whisper", lambda: m._Whisper.model())]
        for i, (name, f) in enumerate(steps):
            self.status.emit(f"Loading {name} ({i + 1} of {len(steps)})…")
            try:
                f()
            except Exception as e:
                self.status.emit(f"Could not load {name}: {e}")
                READY.set()
                return
        READY.set()
        self.status.emit("Ready. Press Record and speak.")


class Hear(QThread):
    """Each engine in turn on one recording; a row as each one finishes."""
    row = pyqtSignal(int, str, str, float)
    done = pyqtSignal(int)

    def __init__(self, n, audio):
        super().__init__()
        self.n, self.audio = n, audio

    def run(self):
        READY.wait()
        with HEAR_LOCK:
            self._run()

    def _run(self):
        for key, _label in ENGINES:
            t = time.perf_counter()
            try:
                if key == "live":
                    text = run_live(self.audio)
                elif key == "whisper":
                    text = m._Whisper.transcribe(self.audio)
                else:
                    text = run_parakeet(key, self.audio)
            except Exception as e:
                text = f"(failed: {e})"
            self.row.emit(self.n, key, text, time.perf_counter() - t)
        self.done.emit(self.n)


class VoiceTest(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Voice test — which engine hears you best")
        self.resize(980, 640)
        self.setStyleSheet("QWidget { background: #1b1d23; color: #e8eaf0; font-family: 'Segoe UI'; }"
                           "QPushButton { background: #3a3f4b; border: none; border-radius: 8px; padding: 10px 22px;"
                           " font-size: 12pt; } QPushButton:hover { background: #4a5060; }"
                           "QPushButton#rec { background: #c0392b; } QPushButton#rec:hover { background: #e74c3c; }"
                           "QTextBrowser { background: #23262e; border: 1px solid #3a3f4b; border-radius: 8px; }"
                           "QProgressBar { background: #23262e; border: none; border-radius: 4px; }"
                           "QProgressBar::chunk { background: #e74c3c; border-radius: 4px; }")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        intro = QLabel("Press <b>Record</b>, say a phrase (for example <i>forgotten but not gone</i>), then "
                       "<b>Stop</b>. Each engine writes what it heard. The time is how long a re-hearing engine needs "
                       "for the phrase, on top of the second Otterly already waits after you pause; Otterly's own "
                       "live engine writes while you talk. Nothing is saved; close the window when you are done.")
        intro.setWordWrap(True)
        intro.setStyleSheet("font-size: 10.5pt; color: #c8ccd6;")
        lay.addWidget(intro)
        row = QHBoxLayout()
        self.btn = QPushButton("●  Record")
        self.btn.setObjectName("rec")
        self.btn.clicked.connect(self.toggle)
        row.addWidget(self.btn)
        self.level = QProgressBar()
        self.level.setRange(0, 100)
        self.level.setTextVisible(False)
        self.level.setFixedHeight(10)
        row.addWidget(self.level, 1)
        self.secs = QLabel("")
        self.secs.setFixedWidth(70)
        row.addWidget(self.secs)
        lay.addLayout(row)
        self.status = QLabel("")
        self.status.setStyleSheet("color: #8a90a0; font-size: 9.5pt;")
        lay.addWidget(self.status)
        self.out = QTextBrowser()
        self.out.setOpenLinks(False)
        lay.addWidget(self.out, 1)
        self.rec = None
        self.n = 0
        self.blocks = {}         # n -> {key: (text, seconds)}
        self.seconds = {}
        self.workers = []
        self.timer = QTimer(self)
        self.timer.setInterval(80)
        self.timer.timeout.connect(self.tick)
        self.warm = Warmup()
        self.warm.status.connect(self.status.setText)
        self.warm.start()
        self.render()

    def toggle(self):
        if self.rec is None:
            self.rec = m._MicRecorder()
            err = self.rec.start()
            if err:
                self.status.setText(err)
                self.rec = None
                return
            self.btn.setText("■  Stop")
            self.btn.setObjectName("")
            self.btn.setStyleSheet("background: #3a3f4b;")
            self.timer.start()
        else:
            audio = self.rec.stop()
            self.rec = None
            self.timer.stop()
            self.level.setValue(0)
            self.secs.setText("")
            self.btn.setText("●  Record")
            self.btn.setStyleSheet("")
            if len(audio) < m.WHISPER_RATE * 0.4:
                self.status.setText("That was too short to hear anything; try again.")
                return
            self.n += 1
            self.blocks[self.n] = {}
            self.seconds[self.n] = len(audio) / m.WHISPER_RATE
            w = Hear(self.n, audio)
            w.row.connect(self.on_row)
            w.done.connect(lambda n: self.render())
            self.workers.append(w)
            w.start()
            self.render()

    def tick(self):
        if self.rec is not None:
            self.level.setValue(int(100 * self.rec.level))
            self.secs.setText(f"{self.rec.seconds():.1f} s")

    def on_row(self, n, key, text, secs):
        self.blocks[n][key] = (text, secs)
        self.render()

    def render(self):
        parts = []
        for n in sorted(self.blocks, reverse=True):
            rows = []
            for key, label in ENGINES:
                if key in self.blocks[n]:
                    text, secs = self.blocks[n][key]
                    when = "while you talk" if key == "live" else f"{secs:.1f} s"
                    rows.append(f"<tr><td style='color:#8a90a0; padding:4px 14px 4px 0; white-space:nowrap'>{label}</td>"
                                f"<td style='padding:4px 14px 4px 0; font-size:12pt'>{html.escape(text) or '<i>(nothing)</i>'}</td>"
                                f"<td style='color:#8a90a0; padding:4px 0; white-space:nowrap' align='right'>{when}</td></tr>")
                else:
                    rows.append(f"<tr><td style='color:#8a90a0; padding:4px 14px 4px 0'>{label}</td>"
                                f"<td style='color:#5a6070'><i>listening to it…</i></td><td></td></tr>")
            parts.append(f"<p style='color:#9aa3b5; margin:14px 0 4px 0'><b>Phrase {n}</b> "
                         f"&nbsp;·&nbsp; {self.seconds[n]:.1f} s of speech</p>"
                         f"<table cellspacing='0' width='100%'>{''.join(rows)}</table>")
        if not parts:
            parts.append("<p style='color:#5a6070'>Your phrases will show here.</p>")
        self.out.setHtml("".join(parts))

    def closeEvent(self, e):
        if self.rec is not None:
            self.rec.stop()
        for w in self.workers:
            w.wait(15000)
        self.warm.wait(30000)
        super().closeEvent(e)


def selftest(wav_path):
    """Feeds a recording instead of the microphone; prints each engine's text and time."""
    import wave
    with wave.open(wav_path) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768.0
    app = QApplication(sys.argv)
    for key, label in ENGINES:
        t = time.perf_counter()
        text = run_live(a) if key == "live" else (m._Whisper.transcribe(a) if key == "whisper" else run_parakeet(key, a))
        print(f"{label:28} {time.perf_counter() - t:5.1f} s  {text}")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--selftest":
        selftest(sys.argv[2])
        sys.exit(0)
    app = QApplication(sys.argv)
    win = VoiceTest()
    win.show()
    win.raise_()
    win.activateWindow()
    sys.exit(app.exec())
