"""PDF 목차(TOC) 페이지를 파싱해서, 쪽수로 소속 섹션을 조회할 수 있는 구조로 만든다."""
import re
from bisect import bisect_right

from pypdf import PdfReader

# "제목 ······· 12" / "1.1 절 이름   15" 처럼 제목과 쪽수 사이에
# 점 리더(마침표 또는 가운뎃점 계열 문자) 또는 공백이 오고, 줄 끝이 숫자로 끝나는 목차 줄 패턴.
# 한글 문서의 목차 점 리더는 ASCII 마침표가 아니라 가운뎃점(·, U+00B7) 등으로 찍히는 경우가 많다.
LEADER_CHARS = ".·‧∙•・"
TOC_LINE_PATTERN = re.compile(rf"^(.+?)[{LEADER_CHARS}\s]{{2,}}(\d+)$")


def extract_pages_text(pdf_path: str, page_numbers: list[int]) -> str:
    """1-based page_numbers에 해당하는 페이지 텍스트를 순서대로 이어 붙인다."""
    reader = PdfReader(pdf_path)
    texts = [reader.pages[page_number - 1].extract_text() for page_number in page_numbers]
    return "\n".join(texts)


def parse_toc(text: str) -> list[dict]:
    """목차 텍스트를 [{"title": str, "page": int}, ...]로 파싱한다."""
    entries = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        match = TOC_LINE_PATTERN.match(line)
        if not match:
            continue
        title, page = match.groups()
        entries.append({"title": title.strip(f" {LEADER_CHARS}"), "page": int(page)})
    return entries


def build_page_lookup(entries: list[dict]):
    """목차 항목을 쪽수 오름차순으로 정렬하고, 특정 쪽이 속한 섹션을 찾는 함수를 함께 반환한다."""
    ordered = sorted(entries, key=lambda e: e["page"])
    pages = [e["page"] for e in ordered]

    def section_for_page(page_number: int) -> dict | None:
        index = bisect_right(pages, page_number) - 1
        if index < 0:
            return None
        return ordered[index]

    return ordered, section_for_page


if __name__ == "__main__":
    import sys

    pdf_path, toc_pages = sys.argv[1], [int(p) for p in sys.argv[2].split(",")]
    toc_text = extract_pages_text(pdf_path, toc_pages)
    toc_entries = parse_toc(toc_text)
    for entry in toc_entries:
        print(entry)
