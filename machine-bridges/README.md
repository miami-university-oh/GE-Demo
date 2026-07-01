# IIoT Machine Bridges — Setup Guide

## Overview

These scripts run on **your PC (192.168.1.16)** and act as real-time bridges between the lab equipment and the IIoT dashboard. They connect to each machine using its native protocol, parse the data, and re-publish it as a WebSocket stream that the dashboard consumes automatically.

| Script | Machine | Protocol | PC Port | Machine IP |
|---|---|---|---|---|
| `haas_bridge.py` | Haas TL-1 | Q-Command TCP | `8765` | `192.168.1.40:5051` |
| `ur5e_bridge.py` | UR5e Cobot | RTDE | `8766` | `192.168.1.15:30004` |

---

## Prerequisites

### 1. Python 3.9+
Download from [https://python.org](https://python.org). During install, check **"Add Python to PATH"**.

### 2. Install dependencies
Open a Command Prompt and run:
```
pip install websockets
```

### 3. Network
Your PC must be on the same local network as the machines (`192.168.1.x`). Verify with:
```
ping 192.168.1.40   ← Haas TL-1
ping 192.168.1.15   ← UR5e
```

---

## Quick Start

1. Copy the entire `machine-bridges` folder to `C:\iiot-bridges\` on your PC
2. Double-click **`start_all_bridges.bat`**
3. Two terminal windows will open — one per machine
4. Open the IIoT Dashboard and navigate to **Makino Lab**
5. Equipment panels automatically switch from **SIM** to **LIVE** badge

---

## Haas TL-1 Setup (`haas_bridge.py`)

### Enable Q-Command on the Haas control
1. On the Haas control panel, press **SETTING**
2. Search for setting **#143** (Remote Q-Command)
3. Set it to **1** (Enabled)
4. Note the machine's IP address (MDI → `NETSTAT` or Settings → Network)

### What data is streamed
| Field | Source |
|---|---|
| Status (IDLE / RUNNING / ALARM) | Q600 |
| Active program name | Q500 |
| Spindle RPM | Q408 |
| Spindle load % | Q410 |
| Feed rate | Q411 |
| X / Z axis positions | Q500 / Q501 |
| Tool number | Q403 |
| Cycle time | Q404 |
| Part count | Q402 |
| Power draw (estimated) | Derived from spindle load |
| Alarm code | Q300 |
| Coolant status | Q409 |

### Troubleshooting
- **"Connection refused"** → Q-Command not enabled (see above), or firewall blocking port 5051. Add a Windows Firewall inbound rule for TCP 5051.
- **Empty responses** → Machine is in E-Stop or powered off.
- **Wrong values** → Some older Haas firmware uses different Q-Command numbers. Check your control's Q-Command list under `HELP → Q-COMMAND`.

---

## UR5e Cobot Setup (`ur5e_bridge.py`)

### No setup needed on the robot
The UR5e's RTDE interface is always enabled on port `30004`. Just make sure:
- The robot is **powered on** and **not in E-Stop**
- Your PC can reach `192.168.1.15` (ping test above)

### What data is streamed
| Field | Source |
|---|---|
| Status (IDLE / RUNNING / ALARM) | Robot mode + safety mode |
| Loaded program name | Dashboard Server (port 29999) |
| TCP position (X/Y/Z mm) | actual_TCP_pose |
| TCP orientation (Rx/Ry/Rz °) | actual_TCP_pose |
| TCP speed (mm/s) | actual_TCP_speed |
| Joint angles (6 joints, °) | actual_q |
| Joint speeds (°/s) | actual_qd |
| Joint torques (Nm, estimated) | actual_current × 3.0 |
| Speed slider % | target_speed_fraction |
| Power draw (W) | voltage × current |
| Safety mode | safety_mode |
| Alarms | Derived from safety_mode |
| Digital outputs | output_bit_registers0_to_31 |

### Troubleshooting
- **"Connection refused"** → Robot is powered off, or another RTDE client is already connected (UR Polyscope limits to 1 RTDE client at a time — close UR Simulator if open).
- **"RTDE start failed"** → Protocol version mismatch. The script uses RTDE v2 which works on all UR software 3.x and 5.x.
- **Safety mode alarms** → The robot tripped a safety stop. Clear it on the teach pendant before the bridge can show RUNNING status.

---

## Auto-Start on Windows Boot (Optional)

To have both bridges start automatically when you log in:

1. Press `Win + R`, type `taskschd.msc`, press Enter
2. Click **Import Task…** in the right panel
3. Import `autostart_bridges.xml` (for Haas TL-1)
4. Repeat for UR5e: duplicate the task and change the script path to `ur5e_bridge.py` and port to `8766`
5. Both bridges will now start silently in the background on every login

---

## Dashboard Integration

The dashboard (`CameraTile` and equipment panels in `MakinoLab.tsx`) automatically:
- Connects to `ws://192.168.1.16:8765` for Haas TL-1
- Connects to `ws://192.168.1.16:8766` for UR5e
- Shows a **LIVE** green badge when connected
- Falls back to **SIM** simulation if the WebSocket is unreachable
- Reconnects automatically if the bridge restarts

To change the PC IP (if your PC's IP changes), update `HAAS_WS_URL` and `UR5E_WS_URL` in:
```
client/src/lib/equipmentData.ts
```

---

## Port Firewall Rules (Windows)

If the dashboard cannot connect to the bridges, add inbound rules:

```
netsh advfirewall firewall add rule name="IIoT Haas Bridge" dir=in action=allow protocol=TCP localport=8765
netsh advfirewall firewall add rule name="IIoT UR5e Bridge" dir=in action=allow protocol=TCP localport=8766
```

Run the above in an **Administrator** Command Prompt.

---

## File Summary

| File | Purpose |
|---|---|
| `haas_bridge.py` | Haas TL-1 Q-Command → WebSocket bridge |
| `ur5e_bridge.py` | UR5e RTDE → WebSocket bridge |
| `start_all_bridges.bat` | Double-click launcher for both bridges |
| `autostart_bridges.xml` | Windows Task Scheduler import for auto-start |
| `README.md` | This file |
