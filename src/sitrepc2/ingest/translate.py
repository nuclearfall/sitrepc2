"""
MarianMT-based translation for sitrepc2 ingestion.

Purpose:
- Translate foreign-language source text (uk / ru) to English
- Enable English-only gazetteer + NLP pipeline
- Zero-cost, offline, deterministic

This module is intentionally minimal.
Translation is a normalization step, not a source of truth.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

import torch
from transformers import MarianMTModel, MarianTokenizer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Supported language pairs
# ---------------------------------------------------------------------------

SUPPORTED_MODELS = {
    "uk": "Helsinki-NLP/opus-mt-uk-en",
    "ru": "Helsinki-NLP/opus-mt-ru-en",
}

# ---------------------------------------------------------------------------
# Model loading (cached)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=None)
def _load_model(lang: str) -> tuple[MarianTokenizer, MarianMTModel]:
    if lang not in SUPPORTED_MODELS:
        raise RuntimeError(f"No MarianMT model for language: {lang}")

    model_name = SUPPORTED_MODELS[lang]
    logger.info("Loading MarianMT model: %s", model_name)

    tokenizer = MarianTokenizer.from_pretrained(model_name)
    model = MarianMTModel.from_pretrained(model_name)

    model.eval()
    return tokenizer, model


# ---------------------------------------------------------------------------
# Translation API
# ---------------------------------------------------------------------------

def translate_to_english(
    text: str,
    source_lang: str,
    *,
    max_length: int = 512,
) -> str:
    """
    Translate text to English using MarianMT.

    Parameters
    ----------
    text : str
        Source text (foreign language)
    source_lang : str
        ISO language code ("uk", "ru")
    max_length : int
        Max token length (truncate if needed)

    Returns
    -------
    str
        English translation

    Raises
    ------
    RuntimeError
        If language unsupported or translation fails
    """
    if not text.strip():
        return ""

    if source_lang.lower() == "en":
        return text

    tokenizer, model = _load_model(source_lang)

    paragraphs = text.split("\n\n")
    out = []

    for p in paragraphs:
        if not p.strip():
            out.append("")
            continue

        batch = tokenizer(
            p,
            return_tensors="pt",
            truncation=True,
            max_length=max_length,
        )

        with torch.no_grad():
            generated = model.generate(
                **batch,
                max_length=max_length,
                num_beams=4,
                early_stopping=True,
            )

        out.append(
            tokenizer.decode(generated[0], skip_special_tokens=True)
        )

    return "\n\n".join(out)

# ---------------------------------------------------------------------------
# Convenience wrapper (optional use)
# ---------------------------------------------------------------------------

class MarianTranslator:
    """
    Minimal translator object for ingestion pipelines.
    """

    def translate(self, text: str, source_lang: Optional[str] = None) -> str:
        if not source_lang:
            raise RuntimeError("source_lang is required for MarianMT translation")

        return translate_to_english(text, source_lang)
