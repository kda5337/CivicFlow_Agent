"""data/knowledge_base/의 쿠팡 FAQ 원본 3개 파일(refund_faq.json, exchange_return_faq.json,
return_policy.json)에서 질문/답변을 모두 모아 하나의 통합 JSON으로 만든다.

원본 파일마다 구조가 다르다:
    - refund_faq.json: qa_list[].answer가 이미 문자열 하나
    - exchange_return_faq.json: episodes[].qa_list[].answer가 이미 문자열 하나
    - return_policy.json: qa_list[].answer가 steps/notes 등으로 세분화된 dict/list
      → flatten_answer()가 이런 답변만 하나의 문자열로 합친다. 내용을 요약하거나
        새로 만들지 않고, 원문 텍스트를 순서대로 이어붙이기만 한다(LLM 가공 없음).

실행:
    cd backend
    python -m app.rag.build_coupang_faq
"""
import json
import sys
from pathlib import Path

_BACKEND_DIR = str(Path(__file__).resolve().parents[2])
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

KNOWLEDGE_BASE_DIR = Path(__file__).resolve().parents[3] / "data" / "knowledge_base"
OUTPUT_PATH = KNOWLEDGE_BASE_DIR / "coupang_faq_combined.json"

REFUND_FAQ_PATH = KNOWLEDGE_BASE_DIR / "refund_faq.json"
EXCHANGE_RETURN_FAQ_PATH = KNOWLEDGE_BASE_DIR / "exchange_return_faq.json"
RETURN_POLICY_PATH = KNOWLEDGE_BASE_DIR / "return_policy.json"


def flatten_answer(value, indent: int = 0) -> list[str]:
    """steps/notes 등으로 세분화된 답변(dict/list)을 원문 그대로 줄 단위 리스트로 펼친다."""
    prefix = "  " * indent
    lines: list[str] = []

    if isinstance(value, str):
        lines.append(f"{prefix}{value}")
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, (dict, list)):
                lines.extend(flatten_answer(item, indent))
            else:
                lines.append(f"{prefix}- {item}")
    elif isinstance(value, dict):
        for key, sub_value in value.items():
            label = key.replace("_", " ")
            if isinstance(sub_value, str):
                lines.append(f"{prefix}{label}: {sub_value}")
            else:
                lines.append(f"{prefix}{label}:")
                lines.extend(flatten_answer(sub_value, indent + 1))
    else:
        lines.append(f"{prefix}{value}")

    return lines


def answer_to_text(answer) -> str:
    if isinstance(answer, str):
        return answer
    return "\n".join(flatten_answer(answer))


def build_refund_faq_records(next_id: int) -> tuple[list[dict], int]:
    data = json.loads(REFUND_FAQ_PATH.read_text(encoding="utf-8"))
    records = []
    for qa in data["qa_list"]:
        records.append(
            {
                "id": next_id,
                "category": data.get("category"),
                "question": qa["question"],
                "answer": answer_to_text(qa["answer"]),
                "source_file": REFUND_FAQ_PATH.name,
                "source_url": data.get("source_url"),
                "published_date": data.get("published_date"),
            }
        )
        next_id += 1
    return records, next_id


def build_exchange_return_faq_records(next_id: int) -> tuple[list[dict], int]:
    data = json.loads(EXCHANGE_RETURN_FAQ_PATH.read_text(encoding="utf-8"))
    records = []
    for episode in data["episodes"]:
        for qa in episode["qa_list"]:
            records.append(
                {
                    "id": next_id,
                    "category": data.get("category"),
                    "question": qa["question"],
                    "answer": answer_to_text(qa["answer"]),
                    "source_file": EXCHANGE_RETURN_FAQ_PATH.name,
                    "source_url": None,
                    "published_date": episode.get("published_date"),
                }
            )
            next_id += 1
    return records, next_id


def build_return_policy_records(next_id: int) -> tuple[list[dict], int]:
    data = json.loads(RETURN_POLICY_PATH.read_text(encoding="utf-8"))
    records = []
    for qa in data["qa_list"]:
        records.append(
            {
                "id": next_id,
                "category": qa.get("section"),
                "question": qa["question"],
                "answer": answer_to_text(qa["answer"]),
                "source_file": RETURN_POLICY_PATH.name,
                "source_url": data.get("source_url"),
                "published_date": None,
            }
        )
        next_id += 1
    return records, next_id


def build() -> list[dict]:
    records: list[dict] = []
    next_id = 1
    for builder in (
        build_refund_faq_records,
        build_exchange_return_faq_records,
        build_return_policy_records,
    ):
        new_records, next_id = builder(next_id)
        records.extend(new_records)

    OUTPUT_PATH.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(records)}건의 질문-답변을 모아 {OUTPUT_PATH}에 저장했습니다.")
    return records


if __name__ == "__main__":
    build()
