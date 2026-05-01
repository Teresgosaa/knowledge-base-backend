from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

LIBREOFFICE_PATH = r"C:\Program Files\LibreOffice\program\soffice.exe"


def render_pdf_to_images(pdf_path: Path, dpi: int = 150) -> List[Path]:
    """Render each page of a PDF to PNG using PyMuPDF."""
    try:
        import fitz  # PyMuPDF
        tmp_work = Path(tempfile.gettempdir()) / f"pdf_{id(pdf_path)}"
        tmp_work.mkdir(parents=True, exist_ok=True)
        doc = fitz.open(str(pdf_path))
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        png_files: List[Path] = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            pix = page.get_pixmap(matrix=mat)
            png_path = tmp_work / f"page_{page_num + 1:03d}.png"
            pix.save(str(png_path))
            png_files.append(png_path)
        doc.close()
        logger.info("Rendered %d PDF pages to PNG", len(png_files))
        return png_files
    except Exception as exc:
        logger.error("Failed to render PDF pages: %s", exc)
        return []

def render_slides_to_images(pptx_path: Path) -> List[Path]:
    """Render each slide of a PPTX to a PNG image using LibreOffice.

    Copies the file to a temp location with ASCII name to avoid
    Cyrillic/spaces issues with LibreOffice on Windows.
    Returns list of PNG file paths (one per slide), sorted by slide number.
    Returns empty list if LibreOffice is not available or conversion fails.
    """
    if not Path(LIBREOFFICE_PATH).exists():
        logger.warning("LibreOffice not found at %s", LIBREOFFICE_PATH)
        return []

    try:
        import shutil as _shutil
        import uuid as _uuid

        # Copy to ASCII temp path to avoid LibreOffice Cyrillic issues
        tmp_work = Path(tempfile.gettempdir()) / f"lo_{_uuid.uuid4().hex[:8]}"
        tmp_work.mkdir(parents=True, exist_ok=True)
        ascii_pptx = tmp_work / "slide.pptx"
        _shutil.copy2(str(pptx_path), str(ascii_pptx))

        out_dir = tmp_work / "out"
        out_dir.mkdir(exist_ok=True)

        result = subprocess.run(
            [
                LIBREOFFICE_PATH,
                "--headless",
                "-env:UserInstallation=file:///C:/tmp/lo_profile",
                "--convert-to", "png",
                "--outdir", str(out_dir),
                str(ascii_pptx),
            ],
            capture_output=True,
            timeout=120,
        )

        if result.returncode != 0:
            logger.error("LibreOffice conversion failed: %s", result.stderr.decode(errors="replace"))

        # LibreOffice creates: slide.png (slide 1), slide2.png (slide 2), etc.
        png_files = sorted(out_dir.glob("slide*.png"))
        logger.info("Rendered %d slides to PNG in %s", len(png_files), out_dir)
        return png_files

    except Exception as exc:
        logger.error("Failed to render slides: %s", exc)
        return []


def _extract_shape_text(shape, lines: List[str]) -> None:
    """Recursively extract text from a shape, including grouped shapes and SmartArt."""
    try:
        if shape.shape_type == 6:  # GROUP
            for child in shape.shapes:
                _extract_shape_text(child, lines)
            return

        if shape.shape_type == 7:  # GRAPHIC_FRAME (SmartArt)
            _NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
            seen: set = set()
            for t_elem in shape.element.iter(f"{{{_NS}}}t"):
                text = (t_elem.text or "").strip()
                if text and text not in seen:
                    seen.add(text)
                    lines.append(f"- {text}")
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


def _try_extract_numbered_structure(slide) -> Optional[List[Tuple[int, str]]]:
    """Detect numbered items on a slide (e.g. staircase diagrams) and pair them.

    Finds shapes whose text is a single digit (1-9) and associates each with
    the horizontally closest non-number shape that has meaningful text.
    Returns sorted list of (number, text) pairs, or None if not found.
    """
    try:
        number_shapes = []
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            text = shape.text_frame.text.strip()
            if text.isdigit() and 1 <= int(text) <= 9:
                cx = shape.left + shape.width // 2
                number_shapes.append((int(text), cx, shape))

        if len(number_shapes) < 3:
            return None

        digit_texts = {str(n) for n, _, _ in number_shapes}

        content_shapes = []
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            text = shape.text_frame.text.strip()
            if not text or text in digit_texts or len(text) < 5:
                continue
            cx = shape.left + shape.width // 2
            content_shapes.append((cx, text, shape))

        if not content_shapes:
            return None

        used: set = set()
        pairs: List[Tuple[int, str]] = []
        for num, num_cx, _ in sorted(number_shapes, key=lambda x: x[0]):
            best_text = None
            best_dist = float("inf")
            for cs_cx, cs_text, cs_shape in content_shapes:
                if id(cs_shape) in used:
                    continue
                dist = abs(num_cx - cs_cx)
                if dist < best_dist:
                    best_dist = dist
                    best_text = cs_text
                    best_shape = cs_shape
            if best_text and best_dist < 2000000:  # ~2 inches threshold
                used.add(id(best_shape))
                title = best_text.split("\n")[0].split("\x0b")[0].strip()
                pairs.append((num, title))

        return pairs if len(pairs) >= 3 else None
    except Exception:
        return None


def extract_pptx_to_markdown(pptx_path: Path) -> str:
    """Convert a PPTX file to structured markdown with per-slide H2 sections.

    Each slide becomes a '## Слайд N: title' section. If numbered items are
    detected (e.g. staircase diagrams with oval numbers), they are output as
    '- Уровень N: text' for clear LLM parsing. All other text follows.
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

        # Try to detect numbered structure (staircase / progression diagrams)
        numbered = _try_extract_numbered_structure(slide)
        numbered_texts: set = set()

        if numbered:
            parts.append("Пронумерованные элементы:")
            for num, text in numbered:
                parts.append(f"- Уровень {num}: {text}")
                numbered_texts.add(text.split("\n")[0].split("\x0b")[0].strip()[:50])
            parts.append("")

        # All other text with X-position hints for spatial understanding
        slide_width = prs.slide_width or 1
        body_lines: List[str] = []
        for shape in slide.shapes:
            if shape is title_shape:
                continue
            if not hasattr(shape, "left") or shape.left is None:
                continue
            x_pct = int(shape.left / slide_width * 100)
            lines: List[str] = []
            _extract_shape_text(shape, lines)
            for line in lines:
                clean = line.lstrip("- ").strip()
                if not clean:
                    continue
                if clean.isdigit() and 1 <= int(clean) <= 9:
                    continue
                if any(clean.startswith(t[:30]) for t in numbered_texts):
                    continue
                body_lines.append(f"[X={x_pct}%] {clean}")

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
