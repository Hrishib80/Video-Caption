

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = ROOT / "docs" / "demo"
SOURCE_VIDEO = ROOT / "videos" / "3554997212b3.mp4"
MAX_DURATION = 32.0

CAPTIONS = [
    {"start": 0.0, "end": 2.9, "text": "a person holding a cell phone in front of a keyboard"},
    {"start": 2.9, "end": 6.2, "text": "a person holding a cell phone in their hand"},
    {"start": 6.2, "end": 10.6, "text": "a black and white sign on a black and white screen"},
    {"start": 10.6, "end": 19.2, "text": "a black and white photo of a white bird"},
    {"start": 19.2, "end": 44.6, "text": "a large group of people sitting in a room"},
    {"start": 44.6, "end": 49.9, "text": "a man in a black shirt is holding a nintendo wii game controller"},
    {"start": 49.9, "end": 64.8, "text": "a man in a suit talking to another man in a suit"},
    {"start": 64.8, "end": 69.1, "text": "a black and white photo of a computer screen"},
    {"start": 69.1, "end": 80.2, "text": "a woman sitting at a table with a microphone"},
    {"start": 80.2, "end": 83.5, "text": "a sign on a wall with a picture of a penguin on it"},
    {"start": 83.5, "end": 89.3, "text": "a man wearing glasses and glasses looking at his cell phone"},
    {"start": 89.3, "end": 91.6, "text": "a series of street signs on a blue background"},
]

SOURCE_URL = "https://www.youtube.com/watch?v=MDaZ31jx2vQ"


def caption_at(time_s: float) -> str | None:
    for entry in CAPTIONS:
        if entry["start"] <= time_s < entry["end"]:
            return entry["text"]
    return None


def wrap_text(text: str, max_chars: int = 46) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join(current + [word])
        if len(candidate) <= max_chars:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines[:2]


def draw_caption(frame: np.ndarray, text: str) -> np.ndarray:
    overlay = frame.copy()
    h, w = overlay.shape[:2]
    lines = wrap_text(text)
    line_height = 28
    pad_x, pad_y = 16, 12
    box_height = pad_y * 2 + line_height * len(lines)
    y0 = h - box_height - 24

    cv2.rectangle(overlay, (24, y0), (w - 24, y0 + box_height), (8, 18, 32), -1)
    cv2.addWeighted(overlay, 0.82, frame, 0.18, 0, frame)

    for idx, line in enumerate(lines):
        y = y0 + pad_y + (idx + 1) * line_height - 8
        cv2.putText(
            frame,
            line,
            (40, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            (245, 248, 255),
            2,
            cv2.LINE_AA,
        )
    return frame


def write_srt(path: Path, captions: list[dict], max_end: float) -> None:
    lines: list[str] = []
    for idx, entry in enumerate(captions, 1):
        if entry["start"] >= max_end:
            break
        end = min(entry["end"], max_end)
        lines.append(str(idx))
        lines.append(f"{format_srt(entry['start'])} --> {format_srt(end)}")
        lines.append(entry["text"])
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def format_srt(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    hours, ms = divmod(ms, 3600000)
    minutes, ms = divmod(ms, 60000)
    secs, ms = divmod(ms, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def main() -> None:
    if not SOURCE_VIDEO.exists():
        raise SystemExit(f"Source video not found: {SOURCE_VIDEO}")

    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    output_video = DEMO_DIR / "captioned-demo.mp4"
    output_json = DEMO_DIR / "captions.json"
    output_srt = DEMO_DIR / "captions.srt"

    demo_captions = [c for c in CAPTIONS if c["start"] < MAX_DURATION]
    write_srt(output_srt, CAPTIONS, MAX_DURATION)

    payload = {
        "source_url": SOURCE_URL,
        "duration": MAX_DURATION,
        "captions": demo_captions,
        "model": "nlpconnect/vit-gpt2-image-captioning",
    }
    output_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    cap = cv2.VideoCapture(str(SOURCE_VIDEO))
    if not cap.isOpened():
        raise SystemExit(f"Cannot open video: {SOURCE_VIDEO}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    max_frames = int(MAX_DURATION * fps)

    writer = cv2.VideoWriter(
        str(output_video),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )

    frame_idx = 0
    while frame_idx < max_frames:
        ret, frame = cap.read()
        if not ret:
            break
        time_s = frame_idx / fps
        caption = caption_at(time_s)
        if caption:
            frame = draw_caption(frame, caption)
        writer.write(frame)
        frame_idx += 1

    cap.release()
    writer.release()

    print(f"Wrote {output_video}")
    print(f"Wrote {output_json}")
    print(f"Wrote {output_srt}")


if __name__ == "__main__":
    main()
