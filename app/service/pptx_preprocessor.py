from __future__ import annotations

import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


def _extract_shape_text(shape, lines: List[str]) -> None:
    """Recursively extract text from a shape, including grouped shapes."""
    try:
        # Grouped shape — recurse into children
        if shape.shape_type == 6:  # MSO_SHAPE_TYPE.GROUP
            for child in shape.shapes:
                _extract_shape_text(child, lines)
            return

        if not shape.has_text_frame:
            return

        for para in shape.text_frame.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            level = getattr(para, "level", 0) or 0
            prefix = "  " * level + "- " if level else "- "
            lines.append(f"{prefix}{text}")
    except Exception:
        pass


def extract_pptx_to_markdown(pptx_path: Path) -> str:
    """Convert a PPTX file to structured markdown with per-slide H2 sections.

    Each slide becomes a '## Слайд N: title' section so downstream chunkers
    and the layered-graph builder can recognise slide boundaries.
    Handles grouped shapes (SmartArt, staircase diagrams, etc.) recursively.
    Speaker notes are appended as italicised text after the slide body.
    Returns an empty string if python-pptx is unavailable or the file cannot
    be opened.
    """
    try:
        from pptx import Presentation  # type: ignore
    except ImportError:
        logger.warning("python-pptx is not installed; PPTX pre-processing skipped")
        return ""

    try:
        prs = Presentation(str(pptx_path))
    except Exception as exc:
        logger.error("Cannot open PPTX %s: %s", pptx_path.name, exc)
        return ""

    parts: List[str] = [f"# {pptx_path.stem}", ""]

    for idx, slide in enumerate(prs.slides, 1):
        title_shape = slide.shapes.title
        title = ""
        if title_shape and title_shape.has_text_frame:
            title = title_shape.text_frame.text.strip()

        header = f"## Слайд {idx}"
        if title:
            header += f": {title}"
        parts.append(header)

        body_lines: List[str] = []
        for shape in slide.shapes:
            if shape is title_shape:
                continue
            _extract_shape_text(shape, body_lines)

        parts.extend(body_lines)

        try:
            if slide.has_notes_slide:
                tf = slide.notes_slide.notes_text_frame
                if tf and tf.text.strip():
                    parts.append(f"*Заметки: {tf.text.strip()}*")
        except Exception:
            pass

        parts.append("")

    return "\n".join(parts)
