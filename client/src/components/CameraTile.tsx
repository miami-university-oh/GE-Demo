/* ============================================================
   CameraTile.tsx — YOLO Camera Feed Tile
   Design: Aerospace HMI / SCADA Control Room
   Supports:
     - Live HLS stream via hls.js (when streamUrl is set)
     - Simulated canvas fallback (when no stream URL)
   YOLO overlay: bounding boxes, PPE compliance, safety zones
   ============================================================ */

import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AlertTriangle, Camera, Eye, FileText, Radio, Shield, Users, Wifi, WifiOff } from 'lucide-react';
import Hls from 'hls.js';
import type { YOLOCameraData, BoundingBox } from '@/lib/cameraData';

interface CameraTileProps {
  camera: YOLOCameraData;
  onRequestReport?: () => void;
  expanded?: boolean;
  onExpand?: () => void;
}

// ── Simulated video background ────────────────────────────────
function SimulatedVideo({ alarmActive }: { alarmActive: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const frameRef = useRef<number>(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let frame = 0;
    function draw() {
      if (!canvas || !ctx) return;
      const W = canvas.width;
      const H = canvas.height;

      const grad = ctx.createLinearGradient(0, 0, 0, H);
      grad.addColorStop(0, '#0a1628');
      grad.addColorStop(0.5, '#071020');
      grad.addColorStop(1, '#050d1a');
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, W, H);

      ctx.strokeStyle = 'rgba(96,165,250,0.04)';
      ctx.lineWidth = 0.5;
      for (let x = 0; x < W; x += 40) {
        ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke();
      }
      for (let y = 0; y < H; y += 40) {
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
      }

      const imageData = ctx.getImageData(0, 0, W, H);
      const data = imageData.data;
      for (let i = 0; i < data.length; i += 4 * 8) {
        const noise = (Math.random() - 0.5) * 12;
        data[i] = Math.max(0, Math.min(255, data[i] + noise));
        data[i + 1] = Math.max(0, Math.min(255, data[i + 1] + noise));
        data[i + 2] = Math.max(0, Math.min(255, data[i + 2] + noise));
      }
      ctx.putImageData(imageData, 0, 0);

      const scanY = (frame * 2) % H;
      const scanGrad = ctx.createLinearGradient(0, scanY - 4, 0, scanY + 4);
      scanGrad.addColorStop(0, 'rgba(96,165,250,0)');
      scanGrad.addColorStop(0.5, 'rgba(96,165,250,0.06)');
      scanGrad.addColorStop(1, 'rgba(96,165,250,0)');
      ctx.fillStyle = scanGrad;
      ctx.fillRect(0, scanY - 4, W, 8);

      if (alarmActive) {
        ctx.fillStyle = `rgba(239,68,68,${0.04 + Math.sin(frame * 0.15) * 0.03})`;
        ctx.fillRect(0, 0, W, H);
      }

      frame++;
      frameRef.current = requestAnimationFrame(draw);
    }
    draw();
    return () => cancelAnimationFrame(frameRef.current);
  }, [alarmActive]);

  return (
    <canvas
      ref={canvasRef}
      width={640}
      height={360}
      className="absolute inset-0 w-full h-full"
      style={{ objectFit: 'cover' }}
    />
  );
}

// ── Detect stream type ───────────────────────────────────────
function isMjpegStream(url: string): boolean {
  // MJPEG streams typically come from /video_feed endpoints
  // HLS streams end in .m3u8
  return !url.endsWith('.m3u8') && !url.includes('.m3u8');
}

// ── Live MJPEG stream (RealSense / Flask) ─────────────────────
function MjpegVideo({
  streamUrl,
  alarmActive,
  onError,
}: {
  streamUrl: string;
  alarmActive: boolean;
  onError: () => void;
}) {
  return (
    <img
      src={streamUrl}
      alt="Live MJPEG stream"
      className="absolute inset-0 w-full h-full"
      style={{
        objectFit: 'cover',
        filter: alarmActive ? 'brightness(0.85) saturate(1.2)' : 'none',
      }}
      onError={onError}
    />
  );
}

// ── Live HLS video player ─────────────────────────────────────
function LiveVideo({
  streamUrl,
  alarmActive,
  onError,
}: {
  streamUrl: string;
  alarmActive: boolean;
  onError: () => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const hlsRef = useRef<Hls | null>(null);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    function cleanup() {
      if (hlsRef.current) {
        hlsRef.current.destroy();
        hlsRef.current = null;
      }
    }

    if (Hls.isSupported()) {
      const hls = new Hls({
        lowLatencyMode: true,
        backBufferLength: 2,
        maxBufferLength: 4,
        maxMaxBufferLength: 6,
        liveSyncDurationCount: 1,
        liveMaxLatencyDurationCount: 3,
        enableWorker: true,
      });
      hlsRef.current = hls;
      hls.loadSource(streamUrl);
      hls.attachMedia(video);
      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        video.play().catch(() => {});
      });
      hls.on(Hls.Events.ERROR, (_event, data) => {
        if (data.fatal) {
          onError();
        }
      });
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
      // Safari native HLS
      video.src = streamUrl;
      video.play().catch(() => {});
      video.onerror = onError;
    } else {
      onError();
    }

    return cleanup;
  }, [streamUrl]);

  return (
    <video
      ref={videoRef}
      className="absolute inset-0 w-full h-full"
      style={{
        objectFit: 'cover',
        filter: alarmActive ? 'brightness(0.85) saturate(1.2)' : 'none',
      }}
      muted
      autoPlay
      playsInline
    />
  );
}

// ── YOLO bounding box overlay ─────────────────────────────────
function DetectionOverlay({ detections, width, height }: {
  detections: BoundingBox[];
  width: number;
  height: number;
}) {
  return (
    <svg
      className="absolute inset-0 w-full h-full"
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      style={{ pointerEvents: 'none' }}
    >
      {detections.map(det => {
        const x = det.x * width;
        const y = det.y * height;
        const w = det.w * width;
        const h = det.h * height;
        const conf = Math.round(det.confidence * 100);
        return (
          <g key={det.id}>
            {/* Corner bracket style */}
            <line x1={x} y1={y + 6} x2={x} y2={y} stroke={det.color} strokeWidth="1.5" />
            <line x1={x} y1={y} x2={x + 8} y2={y} stroke={det.color} strokeWidth="1.5" />
            <line x1={x + w - 8} y1={y} x2={x + w} y2={y} stroke={det.color} strokeWidth="1.5" />
            <line x1={x + w} y1={y} x2={x + w} y2={y + 6} stroke={det.color} strokeWidth="1.5" />
            <line x1={x} y1={y + h - 6} x2={x} y2={y + h} stroke={det.color} strokeWidth="1.5" />
            <line x1={x} y1={y + h} x2={x + 8} y2={y + h} stroke={det.color} strokeWidth="1.5" />
            <line x1={x + w - 8} y1={y + h} x2={x + w} y2={y + h} stroke={det.color} strokeWidth="1.5" />
            <line x1={x + w} y1={y + h - 6} x2={x + w} y2={y + h} stroke={det.color} strokeWidth="1.5" />
            <rect x={x} y={y - 14} width={w} height={13} fill={`${det.color}22`} />
            <text
              x={x + 3} y={y - 4}
              fill={det.color}
              fontSize="9"
              fontFamily="'IBM Plex Mono', monospace"
              fontWeight="600"
            >
              {det.label} {conf}%
            </text>
          </g>
        );
      })}
    </svg>
  );
}

// ── Main CameraTile ───────────────────────────────────────────
export function CameraTile({ camera, onRequestReport, expanded = false, onExpand }: CameraTileProps) {
  const [showReport, setShowReport] = useState(false);
  const [streamError, setStreamError] = useState(false);

  const hasLiveStream = !!camera.streamUrl && !streamError;
  const isLive = hasLiveStream && camera.status === 'live';

  const ppeRate = camera.ppeCompliance.total > 0
    ? Math.round((camera.ppeCompliance.compliant / camera.ppeCompliance.total) * 100)
    : 100;

  const ts = new Date(camera.frameTs);
  const timeStr = ts.toLocaleTimeString('en-US', { hour12: false });

  return (
    <div
      className="flex flex-col rounded overflow-hidden"
      style={{
        background: 'oklch(0.10 0.025 240)',
        border: camera.alarmActive
          ? '1px solid rgba(239,68,68,0.50)'
          : '1px solid oklch(1 0 0 / 8%)',
        boxShadow: camera.alarmActive ? '0 0 16px rgba(239,68,68,0.15)' : 'none',
      }}
    >
      {/* ── Header ── */}
      <div
        className="flex items-center justify-between px-3 py-2 flex-wrap gap-y-1"
        style={{ borderBottom: '1px solid oklch(1 0 0 / 8%)', background: 'oklch(0.12 0.025 240)' }}
      >
        <div className="flex items-center gap-2">
          <Camera size={11} style={{ color: camera.alarmActive ? '#ef4444' : '#60a5fa' }} />
          <span className="text-[11px] font-bold tracking-wider" style={{ color: '#e2e8f0' }}>
            {camera.name}
          </span>
          {/* Live / Simulated badge */}
          {isLive ? (
            <motion.span
              animate={{ opacity: [1, 0.6, 1] }}
              transition={{ duration: 1.5, repeat: Infinity }}
              className="flex items-center gap-1 text-[9px] font-bold tracking-widest px-1.5 py-0.5 rounded"
              style={{ background: 'rgba(34,197,94,0.12)', color: '#22c55e', border: '1px solid rgba(34,197,94,0.30)' }}
            >
              <Radio size={7} />
              LIVE
            </motion.span>
          ) : (
            <span
              className="text-[9px] font-bold tracking-widest px-1.5 py-0.5 rounded"
              style={{ background: 'rgba(96,165,250,0.10)', color: '#60a5fa', border: '1px solid rgba(96,165,250,0.20)' }}
            >
              SIM
            </span>
          )}
          {camera.alarmActive && (
            <motion.span
              animate={{ opacity: [1, 0.3, 1] }}
              transition={{ duration: 0.8, repeat: Infinity }}
              className="text-[9px] font-bold tracking-widest px-1.5 py-0.5 rounded"
              style={{ background: 'rgba(239,68,68,0.15)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.40)' }}
            >
              ⚠ ALARM
            </motion.span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[9px] font-data" style={{ color: 'oklch(0.45 0.015 230)' }}>
            {camera.resolution} · {camera.fps}fps
          </span>
          {camera.status === 'live'
            ? <Wifi size={10} style={{ color: '#22c55e' }} />
            : <WifiOff size={10} style={{ color: '#ef4444' }} />
          }
          {onExpand && (
            <button
              onClick={onExpand}
              className="text-[9px] px-1.5 py-0.5 rounded transition-colors hover:bg-white/10"
              style={{ color: '#60a5fa', border: '1px solid rgba(96,165,250,0.25)' }}
            >
              {expanded ? 'COLLAPSE' : 'EXPAND'}
            </button>
          )}
        </div>
      </div>

      {/* ── Video area ── */}
      <div className="relative" style={{ aspectRatio: '16/9', minHeight: expanded ? 280 : 180 }}>
        {/* Video layer: MJPEG, HLS, or simulated canvas */}
        {hasLiveStream ? (
          isMjpegStream(camera.streamUrl!) ? (
            <MjpegVideo
              streamUrl={camera.streamUrl!}
              alarmActive={camera.alarmActive}
              onError={() => setStreamError(true)}
            />
          ) : (
            <LiveVideo
              streamUrl={camera.streamUrl!}
              alarmActive={camera.alarmActive}
              onError={() => setStreamError(true)}
            />
          )
        ) : (
          <SimulatedVideo alarmActive={camera.alarmActive} />
        )}

        {/* YOLO detection overlay */}
        <DetectionOverlay detections={camera.detections} width={640} height={360} />

        {/* Stream error notice */}
        {camera.streamUrl && streamError && (
          <div
            className="absolute inset-0 flex flex-col items-center justify-center gap-2"
            style={{ background: 'rgba(0,0,0,0.70)' }}
          >
            <WifiOff size={20} style={{ color: '#ef4444' }} />
            <span className="text-[10px] font-semibold" style={{ color: '#fca5a5' }}>
              Stream unavailable — showing simulation
            </span>
            <span className="text-[9px]" style={{ color: 'oklch(0.50 0.015 230)' }}>
              {camera.streamUrl}
            </span>
            <button
              onClick={() => setStreamError(false)}
              className="text-[9px] px-2 py-1 rounded mt-1 hover:bg-white/10 transition-colors"
              style={{ color: '#60a5fa', border: '1px solid rgba(96,165,250,0.30)' }}
            >
              Retry
            </button>
          </div>
        )}

        {/* Timestamp + REC */}
        <div className="absolute top-2 left-2 flex items-center gap-1.5">
          <div className="w-1.5 h-1.5 rounded-full bg-red-500" style={{ boxShadow: '0 0 6px #ef444480' }} />
          <span className="font-data text-[9px] font-semibold" style={{ color: '#ef4444' }}>REC</span>
          <span className="font-data text-[9px]" style={{ color: 'rgba(255,255,255,0.50)' }}>{timeStr}</span>
        </div>

        {/* Detection count badge */}
        <div
          className="absolute top-2 right-2 flex items-center gap-1 px-1.5 py-0.5 rounded"
          style={{ background: 'rgba(0,0,0,0.60)', border: '1px solid rgba(96,165,250,0.25)' }}
        >
          <Eye size={9} style={{ color: '#60a5fa' }} />
          <span className="font-data text-[9px]" style={{ color: '#93c5fd' }}>
            {camera.totalDetections} obj
          </span>
        </div>

        {/* Location label */}
        <div
          className="absolute bottom-2 left-2 px-1.5 py-0.5 rounded"
          style={{ background: 'rgba(0,0,0,0.65)', border: '1px solid rgba(255,255,255,0.10)' }}
        >
          <span className="text-[8px] tracking-wider" style={{ color: 'rgba(255,255,255,0.45)' }}>
            {camera.location}
          </span>
        </div>

        {/* Alarm banner */}
        <AnimatePresence>
          {camera.alarmActive && camera.lastAlarm && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 10 }}
              className="absolute bottom-0 left-0 right-0 flex items-center gap-2 px-3 py-1.5"
              style={{ background: 'rgba(239,68,68,0.85)', backdropFilter: 'blur(4px)' }}
            >
              <AlertTriangle size={10} style={{ color: 'white', flexShrink: 0 }} />
              <span className="text-[9px] font-bold tracking-wide text-white truncate">
                {camera.lastAlarm}
              </span>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* ── Stats row ── */}
      <div
        className="grid grid-cols-4 divide-x divide-white/10"
        style={{ borderTop: '1px solid oklch(1 0 0 / 8%)' }}
      >
        <div className="flex flex-col items-center py-2 gap-0.5">
          <Users size={10} style={{ color: '#22c55e' }} />
          <span className="font-data text-sm font-bold" style={{ color: '#22c55e' }}>
            {camera.personCount}
          </span>
          <span className="text-[8px] tracking-wider uppercase" style={{ color: 'oklch(0.45 0.015 230)' }}>
            Persons
          </span>
        </div>

        <div className="flex flex-col items-center py-2 gap-0.5">
          <Shield size={10} style={{ color: ppeRate === 100 ? '#22c55e' : ppeRate > 50 ? '#f59e0b' : '#ef4444' }} />
          <span
            className="font-data text-sm font-bold"
            style={{ color: ppeRate === 100 ? '#22c55e' : ppeRate > 50 ? '#f59e0b' : '#ef4444' }}
          >
            {ppeRate}%
          </span>
          <span className="text-[8px] tracking-wider uppercase" style={{ color: 'oklch(0.45 0.015 230)' }}>
            PPE OK
          </span>
        </div>

        <div className="flex flex-col items-center py-2 gap-0.5">
          <div className="flex gap-0.5">
            {camera.safetyZones.map(z => (
              <div
                key={z.id}
                className="w-2 h-2 rounded-full"
                style={{ background: z.color, boxShadow: `0 0 4px ${z.color}80` }}
                title={z.label}
              />
            ))}
          </div>
          <span
            className="font-data text-sm font-bold"
            style={{ color: camera.safetyZones.every(z => z.status === 'clear') ? '#22c55e' : '#ef4444' }}
          >
            {camera.safetyZones.filter(z => z.status === 'clear').length}/{camera.safetyZones.length}
          </span>
          <span className="text-[8px] tracking-wider uppercase" style={{ color: 'oklch(0.45 0.015 230)' }}>
            Zones OK
          </span>
        </div>

        <div className="flex flex-col items-center py-2 gap-0.5">
          <button
            onClick={() => { setShowReport(true); onRequestReport?.(); }}
            className="flex flex-col items-center gap-0.5 transition-opacity hover:opacity-80 active:scale-95"
          >
            <FileText size={10} style={{ color: '#a78bfa' }} />
            <span className="font-data text-[11px] font-bold" style={{ color: '#a78bfa' }}>RPT</span>
            <span className="text-[8px] tracking-wider uppercase" style={{ color: 'oklch(0.45 0.015 230)' }}>
              Report
            </span>
          </button>
        </div>
      </div>

      {/* ── Expanded detail ── */}
      {expanded && (
        <div
          className="px-3 py-2 flex flex-col gap-1.5"
          style={{ borderTop: '1px solid oklch(1 0 0 / 8%)' }}
        >
          <span className="text-[9px] tracking-widest uppercase font-semibold" style={{ color: 'oklch(0.45 0.015 230)' }}>
            Safety Zones
          </span>
          {camera.safetyZones.map(z => (
            <div key={z.id} className="flex items-center justify-between">
              <span className="text-[10px]" style={{ color: 'oklch(0.65 0.015 230)' }}>{z.label}</span>
              <span
                className="text-[9px] font-bold tracking-wider px-1.5 py-0.5 rounded"
                style={{
                  background: z.status === 'clear' ? 'rgba(34,197,94,0.12)' : 'rgba(239,68,68,0.12)',
                  color: z.status === 'clear' ? '#22c55e' : '#ef4444',
                  border: `1px solid ${z.status === 'clear' ? 'rgba(34,197,94,0.30)' : 'rgba(239,68,68,0.30)'}`,
                }}
              >
                {z.status === 'clear' ? '● CLEAR' : '⚠ BREACHED'}
              </span>
            </div>
          ))}

          {camera.ppeCompliance.violations.length > 0 && (
            <div className="mt-1 flex flex-col gap-1">
              <span className="text-[9px] tracking-widest uppercase font-semibold" style={{ color: '#f59e0b' }}>
                PPE Violations
              </span>
              {camera.ppeCompliance.violations.map((v, i) => (
                <div key={i} className="flex items-center gap-1.5">
                  <AlertTriangle size={9} style={{ color: '#f59e0b' }} />
                  <span className="text-[10px]" style={{ color: '#fbbf24' }}>{v}</span>
                </div>
              ))}
            </div>
          )}

          {/* Stream URL info */}
          <div className="mt-1 pt-1.5" style={{ borderTop: '1px solid oklch(1 0 0 / 6%)' }}>
            <span className="text-[9px] tracking-widest uppercase font-semibold" style={{ color: 'oklch(0.45 0.015 230)' }}>
              Stream Source
            </span>
            <div className="mt-0.5 font-data text-[9px] truncate" style={{ color: isLive ? '#22c55e' : 'oklch(0.50 0.015 230)' }}>
              {camera.streamUrl
                ? (isLive ? `● LIVE — ${camera.streamUrl}` : `○ OFFLINE — ${camera.streamUrl}`)
                : '○ SIMULATED — no stream URL configured'
              }
            </div>
          </div>
        </div>
      )}

      {/* ── Report modal ── */}
      <AnimatePresence>
        {showReport && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
            style={{ background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(4px)' }}
            onClick={() => setShowReport(false)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="w-full max-w-md rounded-lg p-5 flex flex-col gap-3"
              style={{ background: 'oklch(0.12 0.025 240)', border: '1px solid oklch(1 0 0 / 12%)' }}
              onClick={e => e.stopPropagation()}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <FileText size={13} style={{ color: '#a78bfa' }} />
                  <span className="text-sm font-bold" style={{ color: '#e2e8f0' }}>
                    {camera.name} — Session Report
                  </span>
                </div>
                <button
                  onClick={() => setShowReport(false)}
                  className="text-[10px] px-2 py-1 rounded hover:bg-white/10 transition-colors"
                  style={{ color: 'oklch(0.55 0.015 230)' }}
                >
                  CLOSE
                </button>
              </div>

              <div className="grid grid-cols-2 gap-2">
                {[
                  { label: 'Total Detections', value: camera.totalDetections.toString(), color: '#60a5fa' },
                  { label: 'Persons Detected', value: camera.personCount.toString(), color: '#22c55e' },
                  { label: 'PPE Compliance', value: `${ppeRate}%`, color: ppeRate === 100 ? '#22c55e' : '#f59e0b' },
                  { label: 'Alarm Events', value: camera.alarmActive ? '1 ACTIVE' : '0', color: camera.alarmActive ? '#ef4444' : '#22c55e' },
                ].map(item => (
                  <div
                    key={item.label}
                    className="flex flex-col gap-0.5 p-2.5 rounded"
                    style={{ background: 'oklch(0.15 0.025 240)' }}
                  >
                    <span className="text-[9px] tracking-widest uppercase" style={{ color: 'oklch(0.50 0.015 230)' }}>
                      {item.label}
                    </span>
                    <span className="font-data text-lg font-bold" style={{ color: item.color }}>
                      {item.value}
                    </span>
                  </div>
                ))}
              </div>

              <div className="flex flex-col gap-1.5">
                <span className="text-[9px] tracking-widest uppercase font-semibold" style={{ color: 'oklch(0.45 0.015 230)' }}>
                  Safety Zone Status
                </span>
                {camera.safetyZones.map(z => (
                  <div key={z.id} className="flex items-center justify-between">
                    <span className="text-[10px]" style={{ color: 'oklch(0.65 0.015 230)' }}>{z.label}</span>
                    <span
                      className="text-[9px] font-bold px-1.5 py-0.5 rounded"
                      style={{
                        background: z.status === 'clear' ? 'rgba(34,197,94,0.12)' : 'rgba(239,68,68,0.12)',
                        color: z.status === 'clear' ? '#22c55e' : '#ef4444',
                      }}
                    >
                      {z.status === 'clear' ? 'CLEAR' : 'BREACHED'}
                    </span>
                  </div>
                ))}
              </div>

              <div
                className="text-[9px] font-data pt-2"
                style={{ color: 'oklch(0.45 0.015 230)', borderTop: '1px solid oklch(1 0 0 / 8%)' }}
              >
                Generated: {new Date().toLocaleString()} · {isLive ? 'LIVE STREAM' : 'SIMULATED FEED'}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
