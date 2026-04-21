from __future__ import annotations

import re
from typing import Iterable


def _normalize_segments(text: str) -> list[str]:
    segments = re.split(r"\n\s*\n", text)
    normalized: list[str] = []

    for segment in segments:
        cleaned = re.sub(r"[ \t]+", " ", segment).strip()
        if cleaned:
            normalized.append(cleaned)

    return normalized


def _split_large_segment(segment: str, chunk_size: int) -> Iterable[str]:
    if len(segment) <= chunk_size:
        yield segment
        return

    sentence_parts = re.split(r"(?<=[.!?])\s+", segment)
    buffer = ""

    for part in sentence_parts:
        candidate = f"{buffer} {part}".strip() if buffer else part
        if len(candidate) <= chunk_size:
            buffer = candidate
            continue

        if buffer:
            yield buffer

        if len(part) <= chunk_size:
            buffer = part
            continue

        start = 0
        while start < len(part):
            yield part[start : start + chunk_size]
            start += chunk_size
        buffer = ""

    if buffer:
        yield buffer


def chunk_text(text, chunk_size=500, overlap=100):
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")
    if overlap < 0:
        raise ValueError("overlap cannot be negative")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    if not text or not text.strip():
        return []

    segments = _normalize_segments(text)
    if not segments:
        return []

    chunks: list[str] = []
    current_parts: list[str] = []
    current_length = 0

    for segment in segments:
        for part in _split_large_segment(segment, chunk_size):
            separator = 2 if current_parts else 0
            projected_length = current_length + len(part) + separator

            if current_parts and projected_length > chunk_size:
                joined = "\n\n".join(current_parts).strip()
                if joined:
                    chunks.append(joined)
                    overlap_text = joined[-overlap:].strip() if overlap else ""
                    current_parts = [overlap_text] if overlap_text else []
                    current_length = len(overlap_text)
                else:
                    current_parts = []
                    current_length = 0

            separator = 2 if current_parts else 0
            if current_parts and current_length + len(part) + separator > chunk_size:
                current_parts = []
                current_length = 0
                separator = 0
            current_parts.append(part)
            current_length += len(part) + separator

    if current_parts:
        joined = "\n\n".join(part for part in current_parts if part).strip()
        if joined:
            chunks.append(joined)

    return chunks
