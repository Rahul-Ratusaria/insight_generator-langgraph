from dataclasses import dataclass
from pathlib import Path
import hashlib
import pymupdf as fitz

@dataclass(frozen=True)
class PageData:
    number: int
    text: str
    page_type: str
    has_images: bool


def inspect_pdf(path: Path, start: int = 1, end: int | None = None) -> list[PageData]:
    if not path.is_file() or path.suffix.lower() != ".pdf":
        raise ValueError("A local .pdf file is required")
    results = []
    with fitz.open(path) as doc:
        if doc.is_encrypted:
            raise ValueError("Encrypted PDFs are not supported")
        if not doc.page_count:
            raise ValueError("PDF contains no pages")
        upper = doc.page_count if end is None else min(end, doc.page_count)
        if start < 1 or start > upper:
            raise ValueError("Invalid page range")
        for i in range(start - 1, upper):
            page = doc[i]
            text = page.get_text("text", sort=True).strip()
            has_images = bool(page.get_images(full=False)) or len(page.get_drawings()) > 8
            low = text.lower()
            kind = "table" if any(w in low for w in ("total", "percent", "%", "respondents", "revenue")) else "generic"
            if has_images and len(text) < 200:
                kind = "visual"
            results.append(PageData(i + 1, text, kind, has_images))
    return results


def pdf_fingerprint(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def page_png_data_url(path: Path, number: int, scale: float = 1.35) -> str:
    import base64
    with fitz.open(path) as doc:
        pix = doc[number - 1].get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        data = pix.tobytes("png")
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")
