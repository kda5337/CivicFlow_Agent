# -*- coding: utf-8 -*-
"""eval/metrics.py에 정의된 5개 목표 지표를 실제로 측정하는 종합 평가 스크립트.

    ① 문의 분류 정확도 (Accuracy / Macro F1)
    ② 담당부서 추천 정확도 (정답 부서 일치율)
    ③ RAG 검색 적합도 (Top-3 문서가 기대 부서 FAQ에서 나왔는지)
    ④ 답변 초안 품질 (LLM 심사 근사치, 5점 만점)
    ⑤ 처리시간 단축률 (실측 지연시간 vs 가정한 수작업 기준시간)

③④⑤는 완전 자동 측정이 불가능한 값을 코드로 근사한 것이다 — 각 함수 docstring에
어떤 가정을 깔고 있는지 명시해뒀다. eval_config.py의 두 상수(DEPARTMENT_TO_SOURCE_TABLES,
MANUAL_BASELINE_SECONDS)를 실제 데이터로 교체하면 이 스크립트를 그대로 재사용할 수 있다.

실행:
    cd test
    ../.venv/Scripts/python.exe run_full_eval.py
"""
import json
import statistics
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BACKEND_DIR = _REPO_ROOT / "backend"
_EVAL_DIR = _REPO_ROOT / "eval"
_TEST_DIR = Path(__file__).resolve().parent
load_dotenv(_REPO_ROOT / ".env")
for p in (_BACKEND_DIR, _EVAL_DIR, _TEST_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from pydantic import BaseModel, Field  # noqa: E402

from app.core.llm import get_structured_llm  # noqa: E402
from app.graph.build import get_compiled_graph  # noqa: E402
from app.rag.vectorstore import get_vectorstore  # noqa: E402
from eval_config import DEPARTMENT_TO_SOURCE_TABLES, MANUAL_BASELINE_SECONDS  # noqa: E402
from metrics import check_targets  # noqa: E402
from test_cases import TEST_CASES  # noqa: E402

MERGED_FAQ_COLLECTION = "chroma_merged_faq"
RESULTS_DIR = _TEST_DIR / "results"


# ────────────────────────────────────────────────────────────────
# ①② 문의 분류 / 담당부서 — 전체 파이프라인을 실제로 실행해서 얻는다
# ────────────────────────────────────────────────────────────────
def run_pipeline_cases() -> list[dict]:
    results = []
    for case in TEST_CASES:
        started = time.perf_counter()
        try:
            final_state = get_compiled_graph().invoke(
                {"inquiry_id": f"fulleval-{case['id']}", "raw_text": case["text"], "is_test": True},
            )
            error = None
        except Exception as exc:  # noqa: BLE001 - 평가는 개별 실패도 결과로 남겨야 함
            final_state = {}
            error = f"{type(exc).__name__}: {exc}"
        elapsed = time.perf_counter() - started
        classification = final_state.get("classification") or {}
        results.append({
            "id": case["id"],
            "text": case["text"],
            "expected_department": case["expected_department"],
            "actual_department": classification.get("담당부서"),
            "expected_inquiry_type": case["expected_inquiry_type"],
            "actual_inquiry_type": classification.get("문의유형"),
            "draft_answer": final_state.get("draft_answer"),
            "latency_sec": elapsed,
            "error": error,
        })
        mark = "FAIL" if error else "OK"
        print(f"  [{mark:4s}] {case['id']:8s} 부서={results[-1]['actual_department']!s:10s} "
              f"유형={results[-1]['actual_inquiry_type']!s:8s} {elapsed:.1f}s")
    return results


def compute_accuracy_and_macro_f1(results: list[dict], expected_key: str, actual_key: str) -> tuple[float, float]:
    """Accuracy와 Macro F1을 함께 계산한다. Accuracy는 전체 중 맞은 비율(직관적이지만
    클래스 불균형에 취약), Macro F1은 클래스별 F1의 단순 평균(작은 클래스의 실패도
    큰 클래스와 동등하게 반영) — eval/metrics.py가 요구하는 지표는 F1이라 이걸 최종
    수치로 쓰고, Accuracy는 참고용으로 같이 남긴다."""
    scored = [r for r in results if not r["error"]]
    labels = sorted({r[expected_key] for r in scored} | {r[actual_key] for r in scored if r[actual_key]})
    correct = sum(1 for r in scored if r[actual_key] == r[expected_key])
    accuracy = correct / len(results) if results else 0.0

    f1_scores = []
    for label in labels:
        tp = sum(1 for r in scored if r[actual_key] == label and r[expected_key] == label)
        fp = sum(1 for r in scored if r[actual_key] == label and r[expected_key] != label)
        fn = sum(1 for r in scored if r[actual_key] != label and r[expected_key] == label)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        f1_scores.append(f1)
    macro_f1 = statistics.mean(f1_scores) if f1_scores else 0.0
    return accuracy, macro_f1


# ────────────────────────────────────────────────────────────────
# ③ RAG Top-3 검색 적합도
# ────────────────────────────────────────────────────────────────
def compute_rag_top3_relevance(cases: list[dict]) -> float:
    """retrieve_node가 최종 응답에 내려주는 retrieved_docs에는 사람이 읽는 출처 라벨
    (예: "OO.pdf 7번 질문")만 남고 원본 metadata.source_table은 사라진다("답변에 출처를
    수정 불가 텍스트로만 보여준다"는 설계 때문). "이 문서가 기대 부서의 FAQ에서 온 게
    맞는지" 판정하려면 원본 메타데이터가 필요해서, 같은 질의로 Chroma를 한 번 더 직접
    조회해 top-3의 source_table만 따로 확인한다 — 운영 코드(retrieve.py)는 건드리지
    않고 평가 목적으로만 별도 조회한다.

    "적합"의 정의: top-3 중 하나라도 기대 부서의 FAQ 테이블에서 나왔으면 그 케이스는
    적합으로 센다(Top-3 Precision@k 방식과 동일한 사고방식) — 사람이 문서 하나하나의
    실제 관련성을 판단하는 것의 근사치이지, 완전한 대체재는 아니다.
    """
    vectorstore = get_vectorstore(MERGED_FAQ_COLLECTION)
    hits = 0
    for case in cases:
        docs = vectorstore.similarity_search(case["text"], k=3)
        expected_tables = DEPARTMENT_TO_SOURCE_TABLES.get(case["expected_department"], set())
        if any(doc.metadata.get("source_table") in expected_tables for doc in docs):
            hits += 1
    return hits / len(cases) if cases else 0.0


# ────────────────────────────────────────────────────────────────
# ④ 답변 초안 품질 (LLM 심사 근사치)
# ────────────────────────────────────────────────────────────────
class DraftQualityJudgment(BaseModel):
    점수: int = Field(description="1~5점. 5=근거에 충실하고 정중하며 바로 발송 가능, 1=근거 없이 지어냈거나 무성의함")
    이유: str = Field(description="이 점수를 준 짧은 근거")


JUDGE_PROMPT = """당신은 담당자를 대신해 아래 AI 답변 초안의 품질을 1~5점으로 채점합니다.
채점 기준:
  5점: 문의 내용에 정확히 답하고, 정중하며, 바로 발송해도 될 수준
  3점: 방향은 맞으나 다소 형식적이거나 세부사항이 부족함
  1점: 문의와 무관하거나 무성의함

문의: \"\"\"{text}\"\"\"

AI 답변 초안: \"\"\"{answer}\"\"\"
"""


def judge_draft_quality(text: str, answer: str) -> int | None:
    """실제 "담당자 평가 점수"는 사람만 매길 수 있는 값이다. 이 함수는 그 사람 채점을
    LLM으로 근사하는 회귀 테스트용 대리 지표(LLM-as-judge)다 — 소수 케이스를 실제
    담당자가 채점해 이 점수와의 상관관계를 확인하기 전까지는 참고용으로만 써야 한다.

    이 세션에서 반복적으로 겪은 일시적 DNS/API 연결 오류가 심사 단계에서 나면 전체
    스크립트가 죽어 그때까지 모은 결과까지 다 날아갔다 — 개별 실패를 None으로 남기고
    계속 진행하도록 방어한다(파이프라인 실행부와 동일한 원칙)."""
    if not answer:
        return None
    try:
        llm = get_structured_llm(DraftQualityJudgment)
        result: DraftQualityJudgment = llm.invoke(JUDGE_PROMPT.format(text=text, answer=answer))
        return result.점수
    except Exception as exc:  # noqa: BLE001
        print(f"    ↳ 심사 실패(건너뜀): {type(exc).__name__}: {exc}")
        return None


def compute_answer_quality(results: list[dict]) -> tuple[float, list[int]]:
    scored = [r for r in results if not r["error"] and r["draft_answer"]]
    raw_scores = [judge_draft_quality(r["text"], r["draft_answer"]) for r in scored]
    scores = [s for s in raw_scores if s is not None]
    return (statistics.mean(scores) if scores else 0.0), scores


# ────────────────────────────────────────────────────────────────
# ⑤ 처리시간 단축률
# ────────────────────────────────────────────────────────────────
def compute_time_reduction(results: list[dict]) -> tuple[float, float]:
    """분자(실측 지연시간)는 이번 실행에서 직접 잰 값이라 신뢰할 수 있지만, 분모
    (수작업 기준시간)는 eval_config.MANUAL_BASELINE_SECONDS의 가정값이다 — 실제
    담당자 타임스터디 데이터로 교체하기 전까지 이 지표는 "가정 대비 추정치"로만
    해석해야 한다."""
    scored = [r for r in results if not r["error"]]
    avg_latency = statistics.mean(r["latency_sec"] for r in scored) if scored else 0.0
    reduction_rate = 1 - (avg_latency / MANUAL_BASELINE_SECONDS)
    return avg_latency, reduction_rate


def main():
    print(f"{len(TEST_CASES)}건 파이프라인 실행 중...\n")
    results = run_pipeline_cases()

    inquiry_type_accuracy, inquiry_type_f1 = compute_accuracy_and_macro_f1(
        results, "expected_inquiry_type", "actual_inquiry_type"
    )
    department_accuracy, _ = compute_accuracy_and_macro_f1(
        results, "expected_department", "actual_department"
    )

    print("\nRAG Top-3 적합도 측정 중 (Chroma 직접 조회)...")
    rag_relevance = compute_rag_top3_relevance(TEST_CASES)

    print("답변 초안 품질 측정 중 (LLM 심사)...")
    answer_quality, quality_scores = compute_answer_quality(results)

    avg_latency, time_reduction = compute_time_reduction(results)

    measured = {
        "classification_f1": round(inquiry_type_f1, 4),
        "dept_match_rate": round(department_accuracy, 4),
        "rag_top3_precision": round(rag_relevance, 4),
        "answer_quality_score": round(answer_quality, 3),
        "time_reduction_rate": round(time_reduction, 4),
    }
    passed = check_targets(measured)

    error_count = sum(1 for r in results if r["error"])

    print("\n=== eval/metrics.py TARGETS 대조 ===")
    labels = {
        "classification_f1": ("문의 분류 정확도(F1)", "0.80"),
        "dept_match_rate": ("담당부서 추천 정확도", "0.80"),
        "rag_top3_precision": ("RAG Top-3 적합도", "0.75"),
        "answer_quality_score": ("답변 초안 품질(5점)", "4.00"),
        "time_reduction_rate": ("처리시간 단축률", "0.50"),
    }
    print(f"{'평가 항목':22s} {'실측값':>10s} {'목표':>8s} {'달성':>6s}")
    for key, (name, target_str) in labels.items():
        mark = "PASS" if passed[key] else "FAIL"
        print(f"{name:22s} {measured[key]:>10} {target_str:>8s} {mark:>6s}")

    print(f"\n(참고) 에러 {error_count}/{len(TEST_CASES)}건")
    print(f"(참고) 문의유형 accuracy: {inquiry_type_accuracy:.2%} (F1과 별도 참고용)")
    print(f"(참고) 평균 응답 지연: {avg_latency:.2f}초 vs 수작업 가정 기준 {MANUAL_BASELINE_SECONDS}초 ← 가정값, 실측 데이터로 교체 필요")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / f"full_eval_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(
        json.dumps(
            {
                "measured": measured,
                "targets_passed": passed,
                "error_count": error_count,
                "inquiry_type_accuracy": inquiry_type_accuracy,
                "avg_latency_sec": avg_latency,
                "manual_baseline_sec_assumption": MANUAL_BASELINE_SECONDS,
                "answer_quality_scores": quality_scores,
                "pipeline_results": results,
            },
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\n결과 저장: {out_path}")


if __name__ == "__main__":
    main()
