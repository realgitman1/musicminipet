# 🐱 Desktop Cat Pet

A simple desktop pet that sits on your screen and reacts to what you're doing — automatically.

> Based on code from [squarelike's blog](https://squarelike.tistory.com/4), developed further with Claude 3.
> GIF assets from [GIPHY](https://giphy.com/stickers/whatever-meow-dumdum-H4DSGeanR73ZilCn5o) by Monster Arhar.
> The original author could not be reached; used in good faith for a non-commercial project.

---

## Features

- **Fully automatic** — the cat manages itself, no setup needed beyond launching it
- **CPU-aware** — switches to a focused animation when CPU usage exceeds 40%
- **Music detection** — listens for audio output via PipeWire / PulseAudio
  - When music is playing, the cat stands still and music notes (♩ ♪ ♫ ♬) appear on screen every 0.8 seconds
  - Notes accumulate up to **1,000**, gradually filling your entire screen
  - When music stops, all notes fade away
- **Wanders on its own** when idle
- **Right-click menu** for manual controls

---

## Requirements

- Ubuntu 22.04 / 24.04
- Python 3.10+
- PipeWire or PulseAudio (`pactl` command must be available)

---

## Installation

```bash
# Install pactl if not already present
sudo apt install pulseaudio-utils

# Create a virtual environment
python3 -m venv ~/cat_env
source ~/cat_env/bin/activate

# Install dependencies
pip install PyQt5 psutil
```

---

## Running

```bash
1. source ~/cat_env/bin/activate
python3 cat_pet.py

(or run bash file)
2. ./run_cat.sh
```

To launch automatically on login, add the command above to your **Startup Applications**.

---

## File Structure

```
cat_pet.py
gif/
├── busy.gif     # Displayed when CPU usage is high
├── play.gif     # Displayed when idle and playful
├── walk.gif     # Displayed while wandering
├── idle1.gif    # Standing still (also used while music plays)
├── idle2.gif    # Standing still (alternate)
└── click.gif    # Displayed when clicked
```

---

## Controls

| Action | Effect |
|--------|--------|
| Left click | Cat reacts |
| Drag | Move the cat anywhere on screen |
| Right click | Open menu |
| Menu → Walk | Send the cat wandering |
| Menu → Play | Switch to playful mode |
| Menu → Stay | Make the cat stand still |
| Menu → Quit | Exit |

---

## Notes

- The cat always stays on top of other windows
- Music notes are click-through — windows underneath remain fully usable
- Quitting with many notes on screen is handled gracefully (batch cleanup, no freeze)
- CPU threshold can be adjusted by changing `CPU_BUSY_THRESHOLD` at the top of `cat_pet.py`
