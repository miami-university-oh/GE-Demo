[**IIoT Building Dashboard — TypeScript API**](../../../../../README.md)

***

[IIoT Building Dashboard — TypeScript API](../../../../../README.md) / [client/src/components/CameraTile](../README.md) / CameraTile

# Function: CameraTile()

> **CameraTile**(`camera`): `Element`

Defined in: [client/src/components/CameraTile.tsx:314](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/components/CameraTile.tsx#L314)

Full camera tile component for a single YOLO-monitored camera feed.
Selects the appropriate video renderer based on the stream URL:
- No URL or stream error → `SimulatedVideo` (canvas fallback).
- MJPEG URL → `MjpegVideo` (`<img>` multipart stream).
- HLS `.m3u8` URL → `LiveVideo` (hls.js player).

Renders on top of the video: a `DetectionOverlay` for YOLO bounding
boxes, PPE compliance rate and counts, safety zone status chips, an
alarm banner when active, and a detection count badge. A printable
compliance report is accessible via a dialog.

## Parameters

### camera

`CameraTileProps`

Camera data including stream URL, detections, PPE stats, and safety zones.

## Returns

`Element`
