import React from 'react';
import { CameraTile } from '../components/CameraTile';
import { useCameraStore } from '../stores/cameraStore';

export const Cameras: React.FC = () => {
  const { cam01Feed, cam01YoloFeed } = useCameraStore();

  return (
    <div className="cameras-section">
      <div className="cameras-section-title">LIVE SURVEILLANCE</div>
      <div className="cameras-page-grid">
        <CameraTile label="CAM01: REALSENSE D435i" streamUrl={cam01Feed} isImg={true} />
        <CameraTile label="CAM01: YOLO SAFETY SUPERVISOR" streamUrl={cam01YoloFeed} isImg={true} />
        <CameraTile label="CAM02: PAN TILT ZOOM" />
      </div>
    </div>
  );
};
