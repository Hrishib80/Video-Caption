#!/usr/bin/env python
"""
Veauido CLI entry point.

Usage:
    python run.py serve
    python run.py caption --url SOURCE
"""

from __future__ import annotations

import argparse
import json
import sys

BANNER = r"""
 __     __                 _     _
 \ \   / /__  __ _ _   _(_) __| | ___
  \ \ / / _ \/ _` | | | | |/ _` |/ _ \
   \ V /  __/ (_| | |_| | | (_| | (_) |
    \_/ \___|\__,_|\__,_|_|\__,_|\___/
    Video Captioning - ViT + GPT-2
"""


def cmd_serve(args: argparse.Namespace) -> None:
    """Start the FastAPI/Uvicorn server."""
    import config
    import uvicorn

    print(BANNER)
    print(f"  Host : {config.HOST}")
    print(f"  Port : {config.PORT}")
    print(f"  URL  : {config.PUBLIC_URL}")
    print(f"  Model: {config.MODEL_NAME}")
    print()

    uvicorn.run(
        "server.app:app",
        host=config.HOST,
        port=config.PORT,
        reload=False,
        log_level="info",
    )


def cmd_caption(args: argparse.Namespace) -> None:
    """Caption a single video and print results to stdout."""
    print(BANNER)

    from model.captioner import VideoCaptioner
    from model.pipeline import VideoPipeline
    from model.scene_detector import SceneDetector

    try:
        captioner = VideoCaptioner()
        detector = SceneDetector()
        pipeline = VideoPipeline(captioner, detector)
        result = pipeline.process_video(args.url)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print()
    print("=" * 60)
    print("  RESULTS")
    print("=" * 60)
    print(f"  Video ID       : {result['video_id']}")
    print(f"  Duration       : {result['duration']:.1f}s")
    print(f"  Scenes         : {len(result['captions'])}")
    print(f"  Processing time: {result['processing_time']:.1f}s")
    print()

    for caption in result["captions"]:
        print(f"  [{caption['start']:>6.1f}s - {caption['end']:>6.1f}s]  {caption['text']}")

    print()
    print("-" * 60)
    print(json.dumps(result, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="veauido",
        description="Veauido - Video Captioning System",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    subcommands.add_parser("serve", help="Start the web server")

    caption_parser = subcommands.add_parser("caption", help="Caption a video from the CLI")
    caption_parser.add_argument(
        "--url",
        required=True,
        help="Video URL, file URL, or local video path",
    )

    args = parser.parse_args()

    if args.command == "serve":
        cmd_serve(args)
    elif args.command == "caption":
        cmd_caption(args)


if __name__ == "__main__":
    main()
