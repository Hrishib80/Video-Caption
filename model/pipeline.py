

from __future__ import annotations

import concurrent.futures
import shutil
import time
import uuid
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

import cv2
import numpy as np
from PIL import Image

import config
from model.captioner import VideoCaptioner
from model.scene_detector import SceneDetector


class VideoPipeline:
    """End-to-end workflow: video source to timestamped captions."""

    def __init__(
        self,
        captioner: VideoCaptioner,
        scene_detector: SceneDetector,
    ) -> None:
        self.captioner = captioner
        self.scene_detector = scene_detector

    def process_video(self, source: str) -> dict:
        """Download/copy a video, detect scenes, caption each scene, and return JSON."""
        source = source.strip()
        if not source:
            raise RuntimeError("Video source must not be empty.")

        t0 = time.perf_counter()
        video_id = uuid.uuid4().hex[:12]
        video_path = config.VIDEOS_DIR / f"{video_id}.mp4"

        print()
        print("=" * 60)
        print(f"[pipeline] Video ID : {video_id}")
        print(f"[pipeline] Source   : {source}")
        print("=" * 60)

        print("[pipeline] Acquiring video...")
        self._acquire_video(source, video_path)
        self._ensure_readable_video(video_path)
        print(f"[pipeline] Saved to {video_path}")

        duration = self._get_duration(str(video_path))

        print("[pipeline] Detecting scenes...")
        scenes = self.scene_detector.detect_scenes(str(video_path))
        if not scenes:
            scenes = [{"start": 0.0, "end": duration, "frame_indices": []}]

        print(f"[pipeline] Captioning {len(scenes)} scene(s)...")
        captions: list[dict] = []

        for idx, scene in enumerate(scenes, 1):
            start = float(scene["start"])
            end = float(scene["end"])
            print(f"[pipeline] Scene {idx}/{len(scenes)} ({start:.1f}s - {end:.1f}s)")

            frame_bgr = self.scene_detector.extract_representative_frame(
                str(video_path), start, end
            )
            pil_image = self._bgr_to_pil(frame_bgr)
            caption_text = self.captioner.caption_frame(pil_image)

            captions.append(
                {
                    "start": round(start, 2),
                    "end": round(end, 2),
                    "text": caption_text,
                }
            )
            print(f"[pipeline]   -> {caption_text}")

        elapsed = time.perf_counter() - t0
        print(f"[pipeline] Done in {elapsed:.1f}s")
        print()

        return {
            "success": True,
            "video_id": video_id,
            "video_serve_url": f"/videos/{video_id}.mp4",
            "duration": round(duration, 2),
            "captions": captions,
            "processing_time": round(elapsed, 2),
        }

    @classmethod
    def _acquire_video(cls, source: str, output_path: Path) -> None:
        """Copy a local source or download a remote one into ``output_path``."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        local_path = cls._resolve_local_source(source)
        if local_path is not None:
            if not local_path.exists() or not local_path.is_file():
                raise RuntimeError(f"Local video file not found: {local_path}")
            shutil.copy2(local_path, output_path)
            return

        cls._download_video(source, output_path)
        cls._promote_readable_download(output_path)

    @staticmethod
    def _resolve_local_source(source: str) -> Path | None:
        """Return a local path for plain paths or file:// URLs, otherwise ``None``."""
        parsed = urlparse(source)
        if parsed.scheme == "file":
            if parsed.netloc:
                return Path(f"//{parsed.netloc}{unquote(parsed.path)}")
            return Path(url2pathname(unquote(parsed.path)))

        if parsed.scheme:
            return None

        candidate = Path(source).expanduser()
        if candidate.exists():
            return candidate
        return None

    @staticmethod
    def _parse_max_download_bytes(size: str) -> int:
        """Parse a yt-dlp-style size limit (e.g. ``100M``) into bytes."""
        normalized = size.strip().upper()
        multipliers = {"K": 1024, "M": 1024 ** 2, "G": 1024 ** 3}
        if normalized[-1] in multipliers:
            return int(float(normalized[:-1]) * multipliers[normalized[-1]])
        return int(normalized)

    @staticmethod
    def _download_video(source: str, output_path: Path) -> None:
        """Download a video using yt-dlp with browser impersonation for Cloudflare-protected URLs."""
        try:
            import yt_dlp
            from yt_dlp.networking.impersonate import ImpersonateTarget
        except ImportError as exc:
            raise RuntimeError(
                "yt-dlp is not installed. Run: pip install -r requirements.txt"
            ) from exc

        ydl_opts = {
            "format": (
                "best[ext=mp4][vcodec!=none][acodec!=none]/"
                "best[ext=mp4][vcodec!=none]/"
                "bestvideo[ext=mp4][vcodec!=none]/"
                "best[vcodec!=none]"
            ),
            "max_filesize": VideoPipeline._parse_max_download_bytes(config.MAX_DOWNLOAD_SIZE),
            "outtmpl": str(output_path),
            "noplaylist": True,
            "nooverwrites": True,
            "quiet": True,
            "no_warnings": True,
            # Bypass Cloudflare and similar TLS-fingerprint blocks on direct/generic URLs.
            "impersonate": ImpersonateTarget.from_str("chrome"),
            "extractor_args": {"generic": ["impersonate"]},
        }

        def _run_download() -> None:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([source])

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_run_download)
                future.result(timeout=300)
        except concurrent.futures.TimeoutError as exc:
            raise RuntimeError("Video download timed out after 5 minutes.") from exc
        except yt_dlp.utils.DownloadError as exc:
            message = str(exc).strip() or "unknown error"
            if "impersonation dependency" in message.lower() or "curl_cffi" in message.lower():
                message = (
                    f"{message}\n"
                    "Install browser impersonation support: pip install \"yt-dlp[default,curl-cffi]\""
                )
            raise RuntimeError(f"yt-dlp failed: {message}") from exc

        if output_path.exists() or list(output_path.parent.glob(f"{output_path.stem}*")):
            return

        raise RuntimeError(f"Download succeeded but no output file was created for {output_path.stem}")

    @classmethod
    def _promote_readable_download(cls, output_path: Path) -> None:
        """Ensure ``output_path`` points to a file OpenCV can read as video."""
        candidates = [output_path]
        candidates.extend(
            path
            for path in sorted(output_path.parent.glob(f"{output_path.stem}*"))
            if path.is_file() and path not in candidates
        )

        for candidate in candidates:
            if candidate.exists() and cls._is_readable_video(candidate):
                if candidate != output_path:
                    if output_path.exists():
                        output_path.unlink()
                    candidate.replace(output_path)
                return

        found = ", ".join(path.name for path in candidates if path.exists()) or "none"
        raise RuntimeError(f"Downloaded files did not contain a readable video stream: {found}")

    @staticmethod
    def _ensure_readable_video(video_path: Path) -> None:
        """Validate that OpenCV can open the acquired file."""
        if VideoPipeline._is_readable_video(video_path):
            return
        raise RuntimeError(f"Cannot open acquired video: {video_path}")

    @staticmethod
    def _is_readable_video(video_path: Path) -> bool:
        """Return whether OpenCV can read at least one frame from ``video_path``."""
        cap = cv2.VideoCapture(str(video_path))
        try:
            if not cap.isOpened():
                return False
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            if frame_count <= 0:
                ret, frame = cap.read()
                return bool(ret and frame is not None)
            return True
        finally:
            cap.release()

    @staticmethod
    def _get_duration(video_path: str) -> float:
        """Return video duration in seconds via OpenCV."""
        cap = cv2.VideoCapture(video_path)
        try:
            if not cap.isOpened():
                return 0.0
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0
            return frames / fps if fps > 0 else 0.0
        finally:
            cap.release()

    @staticmethod
    def _bgr_to_pil(frame: np.ndarray) -> Image.Image:
        """Convert an OpenCV BGR frame to a resized PIL RGB image."""
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb)
        return img.resize(config.FRAME_SIZE, Image.LANCZOS)
