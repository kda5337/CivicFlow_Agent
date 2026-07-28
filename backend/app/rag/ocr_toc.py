"""스캔(이미지) PDF에서 pytesseract OCR로 텍스트를 뽑아낸다.

'2022 가천대학교 요람'은 텍스트 레이어가 없는 스캔 PDF라 pdf_toc.py의
pypdf 텍스트 추출로는 내용을 읽을 수 없어, 페이지를 이미지로 렌더링한 뒤
OCR로 텍스트를 인식한다.

사전 준비: Tesseract OCR 엔진 + 한국어 언어팩(kor.traineddata)이 시스템에 설치되어 있어야 한다.

실행:
    cd backend
    python -m app.rag.ocr_toc
"""
import shutil
from pathlib import Path

import fitz  # PyMuPDF
import pytesseract
from PIL import Image

PDF_PATH = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "self_collected"
    / "2022 가천대학교 요람 (총람).pdf"
)

# PATH에 없으면 Windows 기본 설치 경로로 대체 (설치 직후에는 현재 셸의 PATH가 아직 갱신 전일 수 있음).
_WINDOWS_DEFAULT_TESSERACT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if not shutil.which("tesseract") and Path(_WINDOWS_DEFAULT_TESSERACT).exists():
    pytesseract.pytesseract.tesseract_cmd = _WINDOWS_DEFAULT_TESSERACT


def render_page_to_image(pdf_path: Path, page_number: int, zoom: float = 2.0) -> Image.Image:
    """1-based page_number 페이지를 렌더링해 PIL 이미지로 반환한다."""
    doc = fitz.open(pdf_path)
    page = doc[page_number - 1]
    pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
    doc.close()
    return image


def ocr_page(pdf_path: Path, page_number: int) -> str:
    """1-based page_number 페이지를 OCR로 읽어 텍스트를 반환한다."""
    image = render_page_to_image(pdf_path, page_number)
    return pytesseract.image_to_string(image, lang="kor")


if __name__ == "__main__":
    for page_number in (11, 12):
        text = ocr_page(PDF_PATH, page_number)
        print(f"=== {page_number}쪽 ===")
        print(text)
