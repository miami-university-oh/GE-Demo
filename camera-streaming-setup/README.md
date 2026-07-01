# IIoT Dashboard — Camera Streaming Setup

## Overview

This folder contains everything needed to stream the Amcrest CAM-02 (and later the RealSense CAM-01) into the IIoT Building Dashboard using **mediamtx** as an RTSP-to-HLS proxy.

| Item | Value |
|---|---|
| Server IP | `192.168.1.15` (Windows) |
| Camera IP | `192.168.1.108` (Amcrest) |
| HLS stream URL | `http://192.168.1.15:8888/cam02/index.m3u8` |
| API health check | `http://192.168.1.15:9997/v3/paths/list` |

---

## Step 1 — Download mediamtx

1. Go to: **https://github.com/bluenviron/mediamtx/releases/latest**
2. Download: `mediamtx_vX.X.X_windows_amd64.zip`
3. Extract **only** `mediamtx.exe` into this folder (same folder as `mediamtx.yml`)

Your folder should look like:
```
C:\iiot-camera-proxy\
  mediamtx.exe          ← downloaded from GitHub
  mediamtx.yml          ← provided in this package
  start_camera_proxy.bat
  autostart_camera_proxy.xml
  README.md
```

---

## Step 2 — Open Windows Firewall Port

The dashboard browsers need to reach port `8888` on this server.

1. Open **Windows Defender Firewall with Advanced Security**
2. Click **Inbound Rules** → **New Rule**
3. Select **Port** → TCP → Specific port: `8888`
4. Allow the connection → apply to all profiles
5. Name it: `IIoT Camera HLS`

---

## Step 3 — Start the Proxy

**Option A — Manual (for testing):**
Double-click `start_camera_proxy.bat`

You should see output like:
```
INF [path cam02] [source rtspSource] connecting to source
INF [path cam02] [source rtspSource] ready: 1 track (H264)
INF [HLS] listener opened on :8888
```

**Option B — Auto-start on boot:**
1. Open Task Scheduler
2. Click **Import Task...**
3. Select `autostart_camera_proxy.xml`
4. Edit the path inside the XML to match where you placed the files
5. Click OK

---

## Step 4 — Test the Stream

Open a browser on any device on the same network and go to:
```
http://192.168.1.15:8888/cam02/index.m3u8
```

It should prompt you to download or play the `.m3u8` file. If VLC is installed, it will open and play the live feed.

Alternatively, paste the URL into **VLC → Media → Open Network Stream**.

---

## Step 5 — Connect to Dashboard

The dashboard is already configured to use this URL for CAM-02. Once the proxy is running, the camera tile in the Makino Lab view will automatically switch from the simulated feed to the live stream.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `mediamtx.exe not found` | Make sure `mediamtx.exe` is in the same folder as `mediamtx.yml` |
| Stream won't connect | Check camera is reachable: `ping 192.168.1.108` in CMD |
| Browser can't reach stream | Check firewall — port 8888 must be open |
| Black screen in dashboard | Camera may be sending H265 — change `subtype=0` to `subtype=1` in the RTSP URL for sub-stream |
| High latency | Reduce `hlsSegmentDuration` to `0.5s` in `mediamtx.yml` |

---

## Adding CAM-01 (RealSense LiDAR)

When ready, see the `cam01` section in `mediamtx.yml` — uncomment the `source:` line and point it to the RealSense RTSP output from the Python script (provided separately).
