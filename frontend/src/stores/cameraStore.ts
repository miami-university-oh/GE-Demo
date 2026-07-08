import { create } from 'zustand';

interface CameraState {
  cam01Feed: string;
  cam01YoloFeed: string;
  cam02HlsUrl: string;
}

export const useCameraStore = create<CameraState>(() => ({
  cam01Feed: '/api/cam01/feed',
  cam01YoloFeed: '/api/cam01/yolo_feed',
  cam02HlsUrl: '/cam02/index.m3u8',
}));
