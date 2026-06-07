"""
Supports reading:
    - .pdf --> pdfplumber (text layer) with pytessaract fallback (scanned)
    - .docx --> python-docx
    - .doc --> LibreOffice ocnversion --> then pyhton-docx
    - .txt/ .md --> plain read
    - .jpg/.jpeg/.png/.webp/.tiff --> pytessarct OCR
    - .csv --> pandas
    - .json / .jsonl --> json/line-by-line
    - Unknown --> raises an UnsupportedFiletTypeError with clear message

RETURNS BACK a unified/centrealixed ReadResult dataclass so every downstream agent always gets the same shape regadless of input format
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pdfplumber
import pandas as pd
from docx import Document
from PIL import Image
import pytesseract
from rich.console import Console

console = Console()

# DATA CLASS OBJECT FOR READRESULT

@dataclass
class ReadResult:
    file_path: str
    extension: str
    raw_text: str
    page_count: int = 1
    metadata: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def has_text(self) -> bool:
        return bool(self.raw_text.strip())
    
# EXCEPTIONS

class UnsupportedFileTypeError(Exception):
    """Raised when the file extension has no registered reader."""

class FileReadError(Exception):
    """Raise when reading fails for a supported format."""


# Internal readers, one per format family

def read_pdf(path: Path) -> ReadResult:
    """
    1) Try pdfplumber (works on PDFs with a text layer).
    2) If extracted test is empty or very short, fall back to pytesseract OCR page0bypage (handles scanned docs uploaded as pdfs).
    """

    warnings: list[str] = []
    pages_text: list[str] = []
    page_count = 0

    try:
        with pdfplumber.open(path) as pdf:
            page_count = len(pdf.pages)
            for page in pdf.pages:
                text = page.extract_text() or ""
                pages_text.append(text)
    except Exception as e:
        raise FileReadError(f"pdfplumber failed on {path.name}: {e}") from e
    
    raw_text = "\n\n".join(pages_text).strip()

    # Metric to gauge scanned doc --> use average character count

    avg_char_count = len(raw_text)/max(page_count, 1)

    if avg_char_count < 20:
        warnings.append(
            "Text layer appears empty or very sparse --> attempting OCR fallback."
        )

        raw_text = read_ocr_pdf(path, page_count, warnings)

    return ReadResult(
        file_path=str(path),
        extension=".pdf",
        raw_text=raw_text,
        page_count=page_count,
        metadata={"page_count": page_count},
        warnings=warnings
    )

def read_ocr_pdf(path, page_count, warnings) -> str:
    """
    Convert each PDF page into a vector image (Rasterize) and run pytesseract OCR
    Falls back gracefully if pdf2image is unavailable
    """

    try:
        from pdf2image import convert_from_path
    except ImportError:
        warnings.append(
            "pdf2image not installed, cannot OCR scanned pdf"
            "Run: pip install pdf2image"
        )
        return ""
    
    try:
        images = convert_from_path(str(path), dpi=200) # DPI = image quality(dots per inch)
        texts = [pytesseract.image_to_string(img) for img in images]
        return "\n\n".join(texts).strip()
    except Exception as e:
        warnings.append(f"OCR failed: {e}")
        return ""

def read_docx(path: Path) -> ReadResult:
    """
    Extract text from a .docx file using python-docx
    """
    try:
       doc = Document(str(path))
       paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
       raw_text = "\n".join(paragraphs)

       return ReadResult(
            file_path=str(path),
            extension=".docx",
            raw_text=raw_text,
            page_count=1,
            metadata={"paragraph_count": len(paragraphs)},
        )
    except Exception as e:
        raise FileReadError(f"python-docx failed on {path.name}: {e}") from e
    
def read_doc_legacy(path: Path) -> ReadResult:
    """
    Convert older .doc files into .docx files using LibreOffice
    Then read using python-docx
    """

    warnings: list[str] = []
    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            subprocess.run(
                [
                    "soffice",
                    "--headless",
                    "--convert-to", "docx",
                    "--outdir", tmp_dir,
                    str(path),
                ],
                check=True,
                capture_output=True,
                timeout=30,
            )
        except FileNotFoundError:
            raise FileReadError(
                "LibreOffce (soffice) is not installed."
                "Cannot convert legacye .doc files"
                "Install LibreOffice or convert to .docx manually"
            )
        except subprocess.CalledProcessError as e:
                raise FileReadError(
                    f"LibreOFfice conversion failed for {path.name}: {e.stderr.decode()}"
                ) from e
        except subprocess.TimeoutExpired:
            raise FileReadError(f"LibreOffice produced no .docx output for {path.name}.")
        
        converted_files = list(Path(tmp_dir).glob("*.docx"))
        if not converted_files:
                raise FileReadError(f"LibreOffice produced no .docx output for {path.name}.")

        result = read_docx(converted_files[0])
        result.file_path = str(path)
        result.extension = ".doc"
        result.warnings.extend(warnings)
        result.warnings.append("Converted from .doc to .docx via LibreOffice")
        return result        
    
def read_txt(path: Path) -> ReadResult:
    """
    Read plain text files (.txt, .md, .log, etc)
    """ 

    try:
        raw_text = path.read_text(encoding="utf-8", errors="replace")
        return ReadResult(
            file_path=str(path),
            extension=path.suffix.lower(),
            raw_text=raw_text,
            page_count=1,
            metadata={
                "char_count": len(raw_text),
                "line_count": raw_text.count("\n")
            }
        )
    except Exception as e:
        raise FileReadError(f"Failed to read {path.name}: {e}") from e
    
def read_image(path: Path) -> ReadResult:
    """
    Extract text from an imag efile using pytesseract OCR
    Useful for photos of ads, printed documents, etc.
    """

    try:
        img = Image.open(str(path))
        raw_text = pytesseract.image_to_string(img)
        return ReadResult(
            file_path=str(path),
            extension=path.suffix.lower(),
            raw_text=raw_text,
            page_count=1,
            metadata={
                "image_size": img.size,
                "image_mode": img.mode
            }
        )
    except Exception as e:
        raise FileReadError(f"Image OCR failed on {path.name}: {e}") from e
    
def read_csv(path: Path) -> ReadResult:
    """
    Read a CSV file and return its content as plain text
    Caps at 500 rows to avoid flooding the context window
    """

    MAX_ROWS = 500
    warnings:list[str] = []

    try:
        df = pd.read_csv(path, nrows=MAX_ROWS)
        total_rows = sum(1 for _ in open(path))-1
        if total_rows > MAX_ROWS:
            warnings.append(
                f"CSV has {total_rows} rows --> only first {MAX_ROWS} loaded"
            )
        raw_text = df.to_string(index=False)

        return ReadResult(
            file_path=str(path),
            extension=".csv",
            raw_text=raw_text,
            page_count=1,
            metadata={
                "rows": min(total_rows, MAX_ROWS),
                "columns": list(df.columns)
            },
            warnings=warnings
        )
    except Exception as e:
        raise FileReadError(f"CSV read failed on {path.name}: {e}") from e
    
def read_json(path: Path) -> ReadResult:
    """
    Read a .json or .jsonl file and return its content as text
    """

    try:
        if path.suffix.lower() == ".jsonl":
            lines = []
            with open(path, encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if i >= 200:
                        break
                    lines.append(line.strip())
            raw_text = "\n".join(lines)
        else:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            raw_text = json.dumps(data, indent=2)

        return ReadResult(
            file_path=str(path),
            extension=path.suffix.lower(),
            raw_text=raw_text,
            page_count=1,
        )
    except Exception as e:
        raise FileReadError(f"JSON read failed on {path.name}: {e}") from e

# OBJECT MAPPING EACH ACCEPTABLE DOCUMENT TO A FUNCTION

READERS = {
    ".pdf": read_pdf,
    ".docx": read_docx,
    ".doc": read_doc_legacy,
    ".txt": read_txt,
    ".md": read_txt,
    ".log": read_txt,
    ".jpg": read_image,
    ".jpeg": read_image,
    ".png": read_image,
    ".webp": read_image,
    ".tiff": read_image,
    ".tif": read_image,
    ".csv": read_csv,
    ".json": read_json,
    ".jsonl": read_json
}

# PUBLIC API

def read_file(file_path: str | Path) -> ReadResult:
    """
    Read a file and return a unified ReadResult

    Params: 
        file_path : str or Path

    Returns:
        ReadResult
    
    Raises:
        FileNotFoundError
        UnsupportedFileTypeError
        FileReadError
    """

    path = Path(file_path).resolve()

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    
    extension = path.suffix.lower()

    if extension not in READERS:
        supported = ", ".join(sorted(READERS.keys()))
        raise UnsupportedFileTypeError(
            f"No reader for '{extension}'. Supported: {supported}"
        )
    
    console.print(f"[dim]Reading [bold]{path.name}[/bold] as {extension}...[/dim]")
    result = READERS[extension](path)

    for w in result.warnings:
        console.print(f" [yellow] {w}/[/yellow]")
    
    console.print(
        f" [green] {len(result.raw_text):,} chars extracted"
        f"({result.page_count} page(s))"
    )

    return result

def read_folder(folder_path:str | Path, recursive: bool = False) -> list[ReadResult]:
    """
    Read all supported files in a folder.

    Params:
        folder_path --> str or Path and contains the ad Documents
        recursive --> if True we will walk subdirectories to find docs too

    Returns:
    list[ReadResult] --> one reault per file and faileus are logged but DO NOT STOP READING THE BATCH OF ADS    
    """
    folder = Path(folder_path).resolve()
    if not folder.is_dir():
        raise NotADirectoryError(f"Not a director: {folder}")
    
    pattern = "**/*" if recursive else "*"

    results: list[ReadResult] = []
    skipped: list[str] = []

    files = sorted(folder.glob(pattern))
    supported_files = [f for f in files if f.is_file() and f.suffix.lower() in READERS]

    console.print(
        f"\n[bold]PropRecon File Reader"
        f"found {len(supported_files)} supported file(s) in [cyan]{folder.name}[/cyan]\n"
    )

    for file in supported_files:
        try:
            result = read_file(file)
            results.append(result)
        except (FileReadError, UnsupportedFileTypeError) as e:
            console.print(f" [red]x {file.name}:[/red] {e}")
            skipped.append(file.name)

    console.print(
        f"\n[bold]Done.[/bold] "
        f"{len(results)} read, {len(skipped)} skipped."
    )
    if skipped:
        console.print(f"[red]Skipped:[/red] {', '.join(skipped)}")
 
    return results









