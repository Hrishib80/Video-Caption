

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import torch
from transformers import AutoTokenizer, VisionEncoderDecoderModel, ViTImageProcessor

import config

if TYPE_CHECKING:
    from PIL import Image


class VideoCaptioner:
    """Load the captioning model and caption PIL images."""

    def __init__(self) -> None:
        print(f"[captioner] Loading model: {config.MODEL_NAME}")
        print(f"[captioner] Device: {config.DEVICE}")
        print(f"[captioner] Cache directory: {config.CACHE_DIR}")

        try:
            self.processor = ViTImageProcessor.from_pretrained(
                config.MODEL_NAME,
                cache_dir=str(config.CACHE_DIR),
            )
            self.tokenizer = AutoTokenizer.from_pretrained(
                config.MODEL_NAME,
                cache_dir=str(config.CACHE_DIR),
            )
            self.model = VisionEncoderDecoderModel.from_pretrained(
                config.MODEL_NAME,
                cache_dir=str(config.CACHE_DIR),
            )

            self.model.to(config.DEVICE)
            self.model.eval()

            total_params = sum(p.numel() for p in self.model.parameters())
            trainable = sum(p.numel() for p in self.model.parameters() if p.requires_grad)
            print("[captioner] Model loaded successfully")
            print(f"[captioner]   Total parameters : {total_params:,}")
            print(f"[captioner]   Trainable params : {trainable:,}")
            print(f"[captioner]   Tokenizer type   : {type(self.tokenizer).__name__}")
            print(f"[captioner]   Vocab size       : {self.tokenizer.vocab_size:,}")

            self._loaded = True
        except Exception as exc:
            print(f"[captioner] Failed to load model: {exc}", file=sys.stderr)
            self._loaded = False
            raise RuntimeError(
                f"Could not load captioning model '{config.MODEL_NAME}'. "
                "Check your internet connection for the first download, or make "
                f"sure the model is already cached. Error: {exc}"
            ) from exc

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def caption_frame(self, pil_image: Image.Image) -> str:
        """Generate a caption for a single PIL image."""
        pixel_values = self.processor(
            images=pil_image,
            return_tensors="pt",
        ).pixel_values.to(config.DEVICE)

        with torch.no_grad():
            generated_ids = self.model.generate(
                pixel_values,
                max_length=config.MAX_CAPTION_LENGTH,
                num_beams=config.NUM_BEAMS,
            )

        return self.tokenizer.decode(
            generated_ids[0],
            skip_special_tokens=True,
        ).strip()

    def caption_frames(self, pil_images: list[Image.Image]) -> list[str]:
        """Caption multiple PIL images one at a time to keep CPU memory low."""
        captions: list[str] = []
        for idx, image in enumerate(pil_images, 1):
            print(f"[captioner] Captioning frame {idx}/{len(pil_images)}...")
            captions.append(self.caption_frame(image))
        return captions
