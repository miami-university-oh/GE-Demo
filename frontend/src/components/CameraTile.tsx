import React from 'react';

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
          <div className="camera-error">Video player not implemented for {label}</div>
        )
      ) : (
        <div className="camera-error">NO FEED</div>
      )}
      <div className="camera-error hidden" style={{ display: 'none' }}>STREAM UNAVAILABLE</div>
    </div>
  );
};
