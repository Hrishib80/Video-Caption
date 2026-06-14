

from __future__ import annotations

import cv2
import numpy as np

import config


class SceneDetector:

    def __init__(
        self,
        threshold: float = config.SCENE_THRESHOLD,
        min_duration: float = config.MIN_SCENE_DURATION,
        sample_fps: int = config.SAMPLE_FPS,
    ) -> None:
        self.threshold = threshold
        self.min_duration = min_duration
        self.sample_fps = max(1, sample_fps)

    def detect_scenes(self, video_path: str) -> list[dict]:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video: {video_path}")

        video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if total_frames <= 0:
            cap.release()
            raise RuntimeError(f"Video has no readable frames: {video_path}")

        duration = total_frames / video_fps
        print(
            f"[scene] Video FPS: {video_fps:.1f} | "
            f"Frames: {total_frames} | Duration: {duration:.1f}s"
        )

        sample_interval = max(1, round(video_fps / self.sample_fps))
        histograms: list[tuple[int, np.ndarray]] = []

        frame_idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % sample_interval == 0:
                histograms.append((frame_idx, self._compute_histogram(frame)))
            frame_idx += 1

        cap.release()

        if len(histograms) < 2:
            return [self._make_scene(0.0, duration, total_frames)]

        boundary_samples = [0]
        for i in range(1, len(histograms)):
            distance = cv2.compareHist(
                histograms[i - 1][1],
                histograms[i][1],
                cv2.HISTCMP_CHISQR,
            )
            if distance > self.threshold:
                boundary_samples.append(i)

        raw_scenes: list[dict] = []
        for boundary_idx, start_sample in enumerate(boundary_samples):
            next_boundary = (
                boundary_samples[boundary_idx + 1]
                if boundary_idx + 1 < len(boundary_samples)
                else len(histograms)
            )

            start_time = histograms[start_sample][0] / video_fps
            end_time = (
                duration
                if next_boundary >= len(histograms)
                else histograms[next_boundary][0] / video_fps
            )
            frame_indices = [
                histograms[sample_idx][0]
                for sample_idx in range(start_sample, next_boundary)
            ]

            raw_scenes.append(
                {
                    "start": round(start_time, 2),
                    "end": round(max(start_time, min(end_time, duration)), 2),
                    "frame_indices": frame_indices,
                }
            )

        scenes = self._merge_short_scenes(raw_scenes, duration)
        print(f"[scene] Detected {len(scenes)} scene(s)")
        return scenes

    def extract_representative_frame(
        self, video_path: str, start: float, end: float
    ) -> np.ndarray:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video: {video_path}")

        video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if total_frames <= 0:
            cap.release()
            raise RuntimeError(f"Video has no readable frames: {video_path}")

        duration = total_frames / video_fps
        mid_time = min(max((start + end) / 2.0, 0.0), max(duration, 0.0))
        mid_frame = min(max(int(mid_time * video_fps), 0), total_frames - 1)

        cap.set(cv2.CAP_PROP_POS_FRAMES, mid_frame)
        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            raise RuntimeError(
                f"Failed to read frame {mid_frame} (t={mid_time:.2f}s) from {video_path}"
            )
        return frame

    @staticmethod
    def _compute_histogram(frame: np.ndarray) -> np.ndarray:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist(
            [hsv],
            [0, 1],
            None,
            [50, 60],
            [0, 180, 0, 256],
        )
        cv2.normalize(hist, hist)
        return hist

    def _merge_short_scenes(
        self, scenes: list[dict], total_duration: float
    ) -> list[dict]:
        if not scenes:
            return []

        merged: list[dict] = []
        for scene in scenes:
            scene_copy = {
                "start": scene["start"],
                "end": scene["end"],
                "frame_indices": list(scene.get("frame_indices", [])),
            }
            scene_duration = scene_copy["end"] - scene_copy["start"]

            if not merged:
                merged.append(scene_copy)
                continue

            previous_duration = merged[-1]["end"] - merged[-1]["start"]
            if scene_duration < self.min_duration or previous_duration < self.min_duration:
                merged[-1]["end"] = scene_copy["end"]
                merged[-1]["frame_indices"].extend(scene_copy["frame_indices"])
            else:
                merged.append(scene_copy)

        merged[-1]["end"] = round(total_duration, 2)
        return [scene for scene in merged if scene["end"] > scene["start"]]

    @staticmethod
    def _make_scene(start: float, end: float, total_frames: int) -> dict:
        """Create a single-scene dict spanning the full video."""
        mid_frame = max(0, total_frames // 2)
        return {
            "start": round(start, 2),
            "end": round(end, 2),
            "frame_indices": [mid_frame],
        }
