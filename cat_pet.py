#!/usr/bin/env python3
"""
🐱 GIF Desktop Cat Pet (PyQt5)
- GIF changes automatically based on CPU usage
- Detects music playback and spawns floating notes
- Walk / Play / Idle / Click reactions
"""

import sys
import os
import random
import math
import subprocess
import psutil
from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtGui import QMovie

# ── GIF paths ───────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GIF_DIR  = os.path.join(BASE_DIR, "gif")

GIF = {
    "busy":  os.path.join(GIF_DIR, "busy.gif"),
    "play":  os.path.join(GIF_DIR, "play.gif"),
    "walk":  os.path.join(GIF_DIR, "walk.gif"),
    "idle1": os.path.join(GIF_DIR, "idle1.gif"),   # also used while music is playing
    "idle2": os.path.join(GIF_DIR, "idle2.gif"),
    "click": os.path.join(GIF_DIR, "click.gif"),
}

CPU_BUSY_THRESHOLD = 40  # busy state threshold (CPU%)

# Individual music notes spawned on screen
MUSIC_NOTES = ["♩", "♪", "♫", "♬"]   # individual notes spawned one by one on screen

# ── Music detection ─────────────────────────────────────────────────

def is_music_playing() -> bool:
    """
    Check audio playback via pactl list short sink-inputs.
    PipeWire format: "108  48  107  PipeWire  float32le 2ch 48000Hz"
    A line exists without CORKED → audio is playing.
    """

    # ── pactl short (fast, PipeWire compatible) ─────────────────────
    try:
        out = subprocess.check_output(
            ["pactl", "list", "short", "sink-inputs"],
            stderr=subprocess.DEVNULL, timeout=2
        ).decode(errors="ignore").strip()

        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            # Skip only lines explicitly marked CORKED; everything else = playing
            if "CORKED" not in line.upper():
                return True
    except Exception:
        pass

    # ── Method 2: pw-dump (native PipeWire, Ubuntu 22.04+) ─────────────
    try:
        out = subprocess.check_output(
            ["pw-dump"],
            stderr=subprocess.DEVNULL, timeout=2
        ).decode(errors="ignore")
        # Check for stream nodes with state=streaming
        if '"state": "streaming"' in out:
            return True
        # Stream/Output/Audio node in running/streaming state
        import json
        nodes = json.loads(out)
        for node in nodes:
            info = node.get("info", {})
            props = info.get("props", {})
            state = info.get("state", "")
            media_class = props.get("media.class", "")
            if "Stream/Output/Audio" in media_class and state in ("streaming", "running"):
                return True
    except Exception:
        pass

    # ── Method 3: check /dev/snd pcm playback device ───────────────────
    # A process holding /dev/snd/pcmCxDxp open = audio playing
    try:
        out = subprocess.check_output(
            ["fuser", "/dev/snd/pcmC0D0p", "/dev/snd/pcmC0D3p"],
            stderr=subprocess.DEVNULL, timeout=1
        ).decode(errors="ignore").strip()
        if out:
            return True
    except Exception:
        pass

    return False


class CatPet(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        # ── State variables ──────────────────────────────────────────
        self.xy        = [100, 800]
        self.to_xy     = [100, 800]
        self.bxy       = [100, 800]
        self.speed     = 3.5
        self.size      = 0.25
        self.direction = 1

        self.state          = "idle1"
        self.cur_gif        = ""
        self.walking        = False
        self.click_cooldown = 0

        # Music state
        self.music_playing     = False   # whether music is currently playing
        self.music_note_tick   = 0       # note spawn cycle counter
        self.note_labels       = []      # list of floating note widgets on screen
        self.note_spawn_timer  = None    # timer that spawns notes

        self.drag_offset  = None
        self._is_dragging = False

        # Speech bubble
        self.bubble_win   = None
        self.bubble_timer = 0

        # ── UI ───────────────────────────────────────────────────────
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground, True)
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.Tool
        )
        self.setWindowTitle("Cat Pet")

        central = QtWidgets.QWidget(self)
        self.setCentralWidget(central)
        central.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)

        self.label = QtWidgets.QLabel(central)
        self.label.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)

        self._build_menu()
        self._load_gif("idle1")
        self.move(*self.xy)
        self.show()

        self.screen = QtWidgets.QApplication.primaryScreen().geometry()

        # ── Timers ──────────────────────────────────────────────────────
        self.main_timer = QtCore.QTimer(self)
        self.main_timer.timeout.connect(self._tick)
        self.main_timer.start(30)

        self.cpu_timer = QtCore.QTimer(self)
        self.cpu_timer.timeout.connect(self._check_cpu)
        self.cpu_timer.start(2000)

        self.music_timer = QtCore.QTimer(self)
        self.music_timer.timeout.connect(self._check_music)
        self.music_timer.start(1500)   # check music every 1.5s

        self.behavior_timer = QtCore.QTimer(self)
        self.behavior_timer.timeout.connect(self._behavior)
        self.behavior_timer.start(4000)

    # ── Load GIF ────────────────────────────────────────────────────

    def _load_gif(self, key):
        if key == self.cur_gif:
            return
        path = GIF.get(key)
        if not path or not os.path.exists(path):
            return
        self.cur_gif = key
        self.movie = QMovie(path)
        self.label.setMovie(self.movie)
        self.movie.start(); self.movie.stop()
        w = int(self.movie.frameRect().width()  * self.size)
        h = int(self.movie.frameRect().height() * self.size)
        self.movie.setScaledSize(QtCore.QSize(w, h))
        self.movie.start()
        self.label.resize(w, h)
        self.resize(w, h)

    # ── Main tick ───────────────────────────────────────────────────

    def _tick(self):
        if self.click_cooldown > 0:
            self.click_cooldown -= 1
            return

        # Speech bubble timer
        if self.bubble_timer > 0:
            self.bubble_timer -= 1
            if self.bubble_timer == 0:
                self._hide_bubble()

        # Lock to idle1 while music plays (notes are spawned by separate timer)
        if self.music_playing and self.state not in ("click", "busy"):
            self.walking = False
            self._load_gif("idle1")
            return

        # Walking
        if self.walking and self.state not in ("busy", "click"):
            self._move_toward()
        else:
            self._load_gif(self.state)

        self.bxy = list(self.xy)

    def _move_toward(self):
        dx = self.to_xy[0] - self.xy[0]
        dy = self.to_xy[1] - self.xy[1]
        dist = math.sqrt(dx*dx + dy*dy)
        if dist < 5:
            self.walking = False
            self._load_gif(random.choice(["idle1", "idle2"]))
            return
        if dx > 1:   self.direction = 1
        elif dx < -1: self.direction = -1
        self.xy[0] += (dx / dist) * self.speed
        self.xy[1] += (dy / dist) * self.speed
        sw, sh = self.screen.width(), self.screen.height()
        self.xy[0] = max(0, min(sw - self.width(),  self.xy[0]))
        self.xy[1] = max(0, min(sh - self.height(), self.xy[1]))
        self.move(int(self.xy[0]), int(self.xy[1]))
        self._update_bubble_pos()
        self._load_gif("walk")

    # ── CPU check ───────────────────────────────────────────────────

    def _check_cpu(self):
        if self.state == "click":
            return
        cpu = psutil.cpu_percent(interval=None)
        if cpu >= CPU_BUSY_THRESHOLD:
            if self.state != "busy":
                self.state = "busy"
                self.walking = False
                self._load_gif("busy")
                self._show_bubble(
                    random.choice(["Working hard...", "So busy!", "CPU is on fire!", "🔥 Full throttle"]), 60
                )
        else:
            if self.state == "busy":
                self.state = random.choice(["idle1", "idle2", "play"])
                self._load_gif(self.state)

    # ── Music detection ─────────────────────────────────────────────

    def _check_music(self):
        if self.state in ("click", "busy"):
            return

        playing = is_music_playing()

        if playing and not self.music_playing:
            # Music started
            self.music_playing  = True
            self.walking = False
            self.state   = "idle1"
            self._load_gif("idle1")
            self._start_note_spawn()

        elif not playing and self.music_playing:
            # Music stopped
            self.music_playing = False
            self._stop_note_spawn()
            self.state = random.choice(["idle1", "idle2"])
            self._load_gif(self.state)

    def _start_note_spawn(self):
        """Start timer that spawns music notes on screen one by one"""
        if self.note_spawn_timer and self.note_spawn_timer.isActive():
            return
        self.note_spawn_timer = QtCore.QTimer(self)
        self.note_spawn_timer.timeout.connect(self._spawn_note)
        self.note_spawn_timer.start(800)   # spawn one note every 0.8s
        self._spawn_note()                 # spawn first note immediately

    def _stop_note_spawn(self):
        """Stop note timer and batch-delete all notes (prevents lag)"""
        if self.note_spawn_timer:
            self.note_spawn_timer.stop()
            self.note_spawn_timer = None
        # hide all immediately (instant, no lag)
        for lbl in self.note_labels:
            try: lbl.hide()
            except: pass
        # start batch deletion (50 at a time)
        self._batch_delete_notes(list(self.note_labels))
        self.note_labels.clear()

    def _batch_delete_notes(self, labels, batch_size=50):
        """Delete note widgets in batches to avoid blocking the main thread"""
        if not labels:
            return
        chunk  = labels[:batch_size]
        rest   = labels[batch_size:]
        for lbl in chunk:
            try: lbl.deleteLater()
            except: pass
        if rest:
            QtCore.QTimer.singleShot(16, lambda: self._batch_delete_notes(rest, batch_size))

    def _spawn_note(self):
        """Spawn a single music note widget at a random position"""
        sw = self.screen.width()
        sh = self.screen.height()

        note_char = random.choice(MUSIC_NOTES)
        size      = random.randint(18, 42)          # vary size
        x         = random.randint(30, sw - 60)
        y         = random.randint(30, sh - 60)
        # random purple/pink/cyan colors
        colors = ["#c084fc", "#f0abfc", "#818cf8", "#67e8f9", "#a78bfa", "#e879f9"]
        color  = random.choice(colors)

        lbl = QtWidgets.QLabel(note_char)
        lbl.setWindowFlags(
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.Tool |
            QtCore.Qt.WindowTransparentForInput   # click-through
        )
        lbl.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        lbl.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, True)
        lbl.setStyleSheet(f"""
            QLabel {{
                color: {color};
                font-size: {size}px;
                background: transparent;
            }}
        """)
        lbl.adjustSize()
        lbl.move(x, y)
        lbl.show()

        self.note_labels.append(lbl)

        # remove oldest note when limit is reached
        MAX_NOTES = 1000
        if len(self.note_labels) > MAX_NOTES:
            old = self.note_labels.pop(0)
            self._fade_out_note(old)

    def _fade_out_note(self, lbl):
        """Fade out and delete a note widget"""
        try:
            effect = QtWidgets.QGraphicsOpacityEffect(lbl)
            lbl.setGraphicsEffect(effect)
            anim = QtCore.QPropertyAnimation(effect, b"opacity", lbl)
            anim.setDuration(600)
            anim.setStartValue(1.0)
            anim.setEndValue(0.0)
            anim.finished.connect(lbl.deleteLater)
            anim.start(QtCore.QAbstractAnimation.DeleteWhenStopped)
        except Exception:
            try: lbl.deleteLater()
            except: pass

    # ── Behavior ────────────────────────────────────────────────────

    def _behavior(self):
        # No behavior changes while music is playing or busy
        if self.state in ("busy", "click") or self.music_playing:
            return

        roll = random.random()
        if roll < 0.35:
            sw, sh = self.screen.width(), self.screen.height()
            self.to_xy  = [random.randint(50, sw-150), random.randint(sh//2, sh-150)]
            self.walking = True
            self.state   = "walk"
        elif roll < 0.55:
            self.walking = False
            self.state   = "play"
            self._load_gif("play")
            self._show_bubble(random.choice(["Let's play! Meow~", "Nyahaha~!", "So fun!", "♪ Happy ♪"]), 80)
        elif roll < 0.75:
            self.walking = False
            self.state   = "idle1"
            self._load_gif("idle1")
            if random.random() < 0.4:
                self._show_bubble(random.choice(["Meow~", "Purrr~", "Sleepy...", "...zZz", "Where are you?"]), 60)
        else:
            self.walking = False
            self.state   = "idle2"
            self._load_gif("idle2")

    # ── Mouse events ────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.drag_offset  = event.globalPos() - self.frameGeometry().topLeft()
            self._is_dragging = False

    def mouseMoveEvent(self, event):
        if event.buttons() == QtCore.Qt.LeftButton and self.drag_offset:
            self._is_dragging = True
            new_pos = event.globalPos() - self.drag_offset
            self.move(new_pos)
            self.xy = [new_pos.x(), new_pos.y()]
            self._update_bubble_pos()

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and not self._is_dragging:
            prev = self.state
            self.state = "click"
            self.walking = False
            self._load_gif("click")
            self.click_cooldown = 50
            QtCore.QTimer.singleShot(1500, lambda: self._restore_state(prev))
            self._show_bubble(random.choice(["Meow!", "Hey~", "What?", "Human~!", "Nyan!"]), 50)
        self._is_dragging = False

    def _restore_state(self, prev):
        self.state = prev if prev != "click" else "idle1"
        self.click_cooldown = 0
        self._load_gif(self.state)
        # restart note spawn if music was playing
        if self.music_playing:
            self._start_note_spawn()

    def closeEvent(self, event):
        """On close: hide all notes immediately, then batch delete to avoid freeze"""
        if self.note_spawn_timer:
            self.note_spawn_timer.stop()
        for lbl in self.note_labels:
            try: lbl.hide()
            except: pass
        self._batch_delete_notes(list(self.note_labels))
        self.note_labels.clear()
        event.accept()

    def contextMenuEvent(self, event):
        self.menu.exec_(self.mapToGlobal(event.pos()))

    # ── Right-click menu ────────────────────────────────────────────

    def _build_menu(self):
        self.menu = QtWidgets.QMenu(self)
        self.menu.addAction("🐾 Walk").triggered.connect(self._manual_walk)
        self.menu.addAction("🎮 Play").triggered.connect(
            lambda: self._set_state("play", "Let's play!", 60))
        self.menu.addAction("😴 Stay").triggered.connect(
            lambda: self._set_state("idle1", "Meow~", 40))
        self.menu.addSeparator()
        self.menu.addAction("❌ Quit").triggered.connect(self.close)

    def _manual_walk(self):
        if self.music_playing:
            return
        sw, sh = self.screen.width(), self.screen.height()
        self.to_xy  = [random.randint(50, sw-150), random.randint(sh//2, sh-150)]
        self.walking = True
        self.state   = "walk"

    def _set_state(self, key, msg, ticks):
        if self.music_playing:
            return
        self.walking = False
        self.state   = key
        self._load_gif(key)
        self._show_bubble(msg, ticks)

    # ── Speech bubble ───────────────────────────────────────────────

    def _show_bubble(self, text, duration_ticks):
        self.bubble_timer = duration_ticks
        if self.bubble_win:
            try: self.bubble_win.close()
            except: pass

        self.bubble_win = QtWidgets.QWidget()
        self.bubble_win.setWindowFlags(
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.Tool
        )
        self.bubble_win.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)

        layout = QtWidgets.QVBoxLayout(self.bubble_win)
        layout.setContentsMargins(0, 0, 0, 0)

        lbl = QtWidgets.QLabel(text)
        lbl.setStyleSheet("""
            QLabel {
                background-color: #1a1a2e;
                color: #e8e8e8;
                border: 2px solid #7c3aed;
                border-radius: 10px;
                padding: 6px 12px;
                font-family: 'Noto Sans KR', 'Monospace';
                font-size: 13px;
                font-weight: bold;
            }
        """)
        layout.addWidget(lbl)
        self.bubble_win.adjustSize()

        bx = int(self.xy[0]) + self.width() + 5
        by = int(self.xy[1])
        if bx + self.bubble_win.width() > self.screen.width():
            bx = int(self.xy[0]) - self.bubble_win.width() - 5
        self.bubble_win.move(bx, by)
        self.bubble_win.show()

    def _hide_bubble(self):
        if self.bubble_win:
            try:
                self.bubble_win.close()
                self.bubble_win = None
            except: pass

    def _update_bubble_pos(self):
        if self.bubble_win:
            try:
                bx = int(self.xy[0]) + self.width() + 5
                by = int(self.xy[1])
                if bx + self.bubble_win.width() > self.screen.width():
                    bx = int(self.xy[0]) - self.bubble_win.width() - 5
                self.bubble_win.move(bx, by)
            except: pass


if __name__ == "__main__":
    print("🐱 Desktop Cat Pet started!")
    print("=" * 40)
    print(f"  Music playing  → idle1 GIF + floating notes ♪")
    print(f"  CPU {CPU_BUSY_THRESHOLD}%↑    → busy GIF")
    print(f"  CPU low        → play / idle GIF")
    print(f"  Left click     → click GIF")
    print(f"  Drag           → move cat")
    print(f"  Right click    → menu")
    print("=" * 40)
    app = QtWidgets.QApplication(sys.argv)
    pet = CatPet()
    sys.exit(app.exec_())
