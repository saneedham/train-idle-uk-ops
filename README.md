# Train Idle: UK Ops

A terminal-based railway management idle game inspired by the UK rail network.

Start in a home city, build out your network, unlock new routes, and manage services to optimise performance, headways, and revenue.

---

## 🚆 Features

- Real UK-inspired network
- Service-based operations (passenger & freight)
- Headway & performance simulation
- Track realism (single/double track, directionality)
- Unlock progression system
- Realism overrides via JSON
- Terminal UI with live map + dashboards

---

## ▶️ Running the Game

### Requirements
- Python 3.11+
- Unix-like terminal (Linux/Mac recommended)

### Run

```bash
python train_idle.py
```

---

## 💾 Save System

The game saves to:

```
train_idle_save_v05661.json
```

---

## 🗺️ Regions & Realism

### Realism Overrides

Located in:

```
realism/devon.json
```

Override per edge:
- tracks
- bidir
- speed_kmh

Commands:

```
realism
realism reload
```

---

## 🎮 Controls

- Arrow Keys: Pan map
- [ ]: Zoom
- + -: Speed
- p: Pause
- o: Ops dashboard

---

## 💻 Commands

```
help
status
home <station>
buy train <model>
services
assign <id> <svc>
unlock
ops
save
```

---

## 🧪 Development

```bash
ruff check .
ruff format .
pytest
```

---

## 📜 License

MIT License

---

## 👤 Author

Simon Needham
