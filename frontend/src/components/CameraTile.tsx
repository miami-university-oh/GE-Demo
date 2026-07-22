import React, { useEffect, useRef, useState } from 'react';
import Hls from 'hls.js';

const HLS_RETRY_MS = 5000;

const HlsVideo: React.FC<{ src: string; label: string }> = ({ src, label }) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    // Safari plays HLS natively; everything else needs hls.js
    if (video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = src;
      return;
    }

    let hls: Hls | null = null;
    let retryTimer: number | undefined;

    const start = () => {
      hls = new Hls();
      hls.loadSource(src);
      hls.attachMedia(video);
      hls.on(Hls.Events.ERROR, (_evt, data) => {
        // The camera may still be connecting when the page loads; keep retrying.
        if (data.fatal) {
          setFailed(true);
          hls?.destroy();
          retryTimer = window.setTimeout(() => {
            setFailed(false);
            start();
          }, HLS_RETRY_MS);
        }
      });
      hls.on(Hls.Events.FRAG_LOADED, () => setFailed(false));
    };

    start();
    return () => {
      window.clearTimeout(retryTimer);
      hls?.destroy();
    };
  }, [src]);

  if (failed) {
    return <div className="camera-error">CONNECTING TO {label}...</div>;
  }
  return <video ref={videoRef} muted autoPlay playsInline />;
};

interface CameraTileProps {
  label: string;
  streamUrl?: string;
  isImg?: boolean;
}

export const CameraTile: React.FC<CameraTileProps> = ({ label, streamUrl, isImg = true }) => {
  return (
    <div className="camera-tile">
      <div className="camera-label">{label}</div>
      {streamUrl ? (
        isImg ? (
          <img src={streamUrl} alt={label} onError={(e) => {
            (e.target as HTMLImageElement).style.display = 'none';
            (e.target as HTMLImageElement).nextElementSibling?.classList.remove('hidden');
          }} />
        ) : (
          <HlsVideo src={streamUrl} label={label} />
        )
      ) : (
        <div className="camera-error">NO FEED</div>
      )}
      <div className="camera-error hidden" style={{ display: 'none' }}>STREAM UNAVAILABLE</div>
    </div>
  );
};
