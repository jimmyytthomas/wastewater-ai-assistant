"""Load the public PDFs and split each page into overlapping text chunks."""

import json
from pathlib import Path

from pypdf import PdfReader

# Project root is the parent of src/, so the scripts work from any working directory.
ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = ROOT / "data" / "public"
METADATA_PATH = ROOT / "data" / "metadata.json"

# About 800 characters per chunk, with the next chunk repeating the last ~150.
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
MIN_CHUNK_CHARS = 50

# Try a paragraph break first, then a single newline, then a sentence ending.
BOUNDARY_MARKERS = ("\n\n", "\n", ". ", "? ", "! ")


def load_chunks():
    """Read metadata.json and return one record per text chunk.

    Each record has an id like "<file>_p<page>_c<n>", the chunk text, a
    1-based page number, and every field from that file's metadata entry.
    """
    documents = json.loads(METADATA_PATH.read_text())
    chunks = []

    for doc in documents:
        reader = PdfReader(str(PUBLIC_DIR / doc["file"]))
        for page_index, page in enumerate(reader.pages):
            page_number = page_index + 1
            text = page.extract_text() or ""
            # Form feeds and nulls show up in some PDFs and are not useful breaks.
            text = text.replace("\x00", "").replace("\f", "\n")

            for chunk_index, piece in enumerate(split_page(text)):
                chunks.append(
                    {
                        "id": f"{doc['file']}_p{page_number}_c{chunk_index}",
                        "text": piece,
                        "page": page_number,
                        **doc,
                    }
                )

    return chunks


def split_page(text):
    """Split one page into ~800 character chunks with ~150 characters of overlap.

    The cut is moved to a paragraph or sentence boundary when one is near the
    target length. Chunks shorter than 50 characters are left out.
    """
    text = text.strip()
    if not text:
        return []

    chunks = []
    start = 0
    length = len(text)

    while start < length:
        target_end = min(start + CHUNK_SIZE, length)
        if target_end == length:
            end = length
        else:
            end = _boundary_before(text, start, target_end)

        piece = text[start:end].strip()
        if len(piece) >= MIN_CHUNK_CHARS:
            chunks.append(piece)

        if end >= length:
            break

        next_start = _overlap_start(text, start, end)
        # A boundary can land on `start` itself. Always advance so this loop ends.
        if next_start <= start:
            next_start = end
        start = next_start

    return chunks


def _boundary_before(text, start, target_end):
    """Return a split point at or just before target_end, on a natural break."""
    # Stay near the target so a chunk does not shrink to a few words.
    window_start = max(start + MIN_CHUNK_CHARS, target_end - 200)
    window = text[window_start:target_end]

    for marker in BOUNDARY_MARKERS:
        index = window.rfind(marker)
        if index != -1:
            return window_start + index + len(marker)

    return target_end


def _overlap_start(text, start, end):
    """Start the next chunk about 150 characters back, on a break when possible."""
    overlap_at = max(start + 1, end - CHUNK_OVERLAP)
    window = text[overlap_at:end]

    for marker in BOUNDARY_MARKERS:
        index = window.find(marker)
        # Keep the marker inside the overlap so the new chunk starts after it.
        if index != -1 and index + len(marker) < len(window):
            return overlap_at + index + len(marker)

    return overlap_at
