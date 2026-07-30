# -*- coding: utf-8 -*-
"""부서 배정(rules_node) + 문의유형 분류(classify_node) 정밀도/성능/토큰 사용량 측정 스크립트.

test_cases.TEST_CASES(50건)를 실제 LangGraph 전체 파이프라인(check_cache→intake→
classify→apply_rules→retrieve→generate→store_cache)에 하나씩 직접 통과시킨다.
is_test=True로 넘겨서, StaffView/App.jsx의 "테스트 (문의 처리)" 화면이 쓰는 것과 동일한
경로로 실행하되(check_cache 조회 생략 + store_cache 저장 생략) query_cache를 오염시키지
않는다. citizen_submissions에도 원래 이 경로는 기록하지 않는다.

실행:
    cd test
    ../.venv/Scripts/python.exe run_classification_eval.py   (Windows)
    python run_classification_eval.py                        (venv 활성화 상태)

결과는 콘솔에 요약 출력 + test/results/classification_eval_<타임스탬프>.json으로 저장.
"""
import json
import statistics
import sys
import time
import traceback
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BACKEND_DIR = _REPO_ROOT / "backend"
load_dotenv(_REPO_ROOT / ".env")
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from langchain_core.callbacks import BaseCallbackHandler  # noqa: E402

from app.graph.build import get_compiled_graph  # noqa: E402
from test_cases import TEST_CASES  # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parent / "results"


class TokenUsageCallback(BaseCallbackHandler):
    """이번 그래프 실행 한 번에 걸린 모든 LLM 호출(intake 관련성 판별, classify, greet,
    generate)의 토큰 사용량을 합산한다. ChatUpstage가 langchain_openai.BaseChatOpenAI를
    상속하므로, 대부분 llm_output.token_usage에 값이 남고 없으면 AIMessage.usage_metadata로
    보완한다(langchain 구조화 출력 경로에서도 콜백은 그대로 호출된다)."""

    def __init__(self):
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.llm_calls = 0

    def on_llm_end(self, response, **kwargs):
        usage = None
        if getattr(response, "llm_output", None):
            usage = response.llm_output.get("token_usage") or response.llm_output.get("usage")
        if usage:
            self.prompt_tokens += usage.get("prompt_tokens", 0)
            self.completion_tokens += usage.get("completion_tokens", 0)
            self.total_tokens += usage.get("total_tokens", 0)
            self.llm_calls += 1
            return

        for generation in getattr(response, "generations", []):
            for gen in generation:
                meta = getattr(getattr(gen, "message", None), "usage_metadata", None)
                if meta:
                    self.prompt_tokens += meta.get("input_tokens", 0)
                    self.completion_tokens += meta.get("output_tokens", 0)
                    self.total_tokens += meta.get("total_tokens", 0)
                    self.llm_calls += 1


def run_one(case: dict) -> dict:
    callback = TokenUsageCallback()
    started = time.perf_counter()
    try:
        final_state = get_compiled_graph().invoke(
            {
                "inquiry_id": f"eval-{case['id']}",
                "raw_text": case["text"],
                "is_test": True,
            },
            config={"callbacks": [callback]},
        )
        elapsed = time.perf_counter() - started
        classification = final_state.get("classification") or {}
        actual_department = classification.get("담당부서")
        actual_inquiry_type = classification.get("문의유형")
        return {
            "id": case["id"],
            "text": case["text"],
            "expected_department": case["expected_department"],
            "actual_department": actual_department,
            "department_correct": actual_department == case["expected_department"],
            "expected_inquiry_type": case["expected_inquiry_type"],
            "actual_inquiry_type": actual_inquiry_type,
            "inquiry_type_correct": actual_inquiry_type == case["expected_inquiry_type"],
            "matched_rules": (final_state.get("rule_flags") or {}).get("matched_rules", []),
            "latency_sec": round(elapsed, 3),
            "prompt_tokens": callback.prompt_tokens,
            "completion_tokens": callback.completion_tokens,
            "total_tokens": callback.total_tokens,
            "llm_calls": callback.llm_calls,
            "error": None,
        }
    except Exception as error:  # noqa: BLE001 - 평가 스크립트는 개별 실패도 결과로 남겨야 함
        elapsed = time.perf_counter() - started
        return {
            "id": case["id"],
            "text": case["text"],
            "expected_department": case["expected_department"],
            "actual_department": None,
            "department_correct": False,
            "expected_inquiry_type": case["expected_inquiry_type"],
            "actual_inquiry_type": None,
            "inquiry_type_correct": False,
            "matched_rules": [],
            "latency_sec": round(elapsed, 3),
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "llm_calls": 0,
            "error": f"{type(error).__name__}: {error}",
        }


def summarize(results: list[dict]) -> dict:
    total = len(results)
    errors = [r for r in results if r["error"]]
    ok = [r for r in results if not r["error"]]

    dept_correct = sum(1 for r in results if r["department_correct"])
    type_correct = sum(1 for r in results if r["inquiry_type_correct"])
    both_correct = sum(1 for r in results if r["department_correct"] and r["inquiry_type_correct"])

    per_department = {}
    for case in TEST_CASES:
        dept = case["expected_department"]
        per_department.setdefault(dept, {"total": 0, "dept_correct": 0, "type_correct": 0})
    for r in results:
        d = per_department[r["expected_department"]]
        d["total"] += 1
        d["dept_correct"] += int(r["department_correct"])
        d["type_correct"] += int(r["inquiry_type_correct"])

    latencies = [r["latency_sec"] for r in ok]
    total_tokens_list = [r["total_tokens"] for r in ok]

    return {
        "total_cases": total,
        "error_count": len(errors),
        "error_rate": round(len(errors) / total, 4),
        "department_accuracy": round(dept_correct / total, 4),
        "inquiry_type_accuracy": round(type_correct / total, 4),
        "both_correct_accuracy": round(both_correct / total, 4),
        "latency_sec": {
            "avg": round(statistics.mean(latencies), 3) if latencies else None,
            "p50": round(statistics.median(latencies), 3) if latencies else None,
            "max": round(max(latencies), 3) if latencies else None,
            "min": round(min(latencies), 3) if latencies else None,
        },
        "tokens": {
            "total_sum": sum(total_tokens_list),
            "avg_per_case": round(statistics.mean(total_tokens_list), 1) if total_tokens_list else None,
        },
        "per_department": per_department,
        "errors": [{"id": r["id"], "error": r["error"]} for r in errors],
    }


def main():
    print(f"총 {len(TEST_CASES)}건 평가 시작...\n")
    results = []
    for i, case in enumerate(TEST_CASES, start=1):
        result = run_one(case)
        results.append(result)
        mark = "OK" if not result["error"] else "FAIL"
        dept_mark = "O" if result["department_correct"] else "X"
        type_mark = "O" if result["inquiry_type_correct"] else "X"
        print(
            f"[{i:2d}/{len(TEST_CASES)}] {result['id']:8s} {mark:4s} "
            f"부서[{dept_mark}]={result['actual_department']!s:10s} "
            f"유형[{type_mark}]={result['actual_inquiry_type']!s:8s} "
            f"{result['latency_sec']:.2f}s  tok={result['total_tokens']}"
        )
        if result["error"]:
            print(f"           ↳ {result['error']}")

    summary = summarize(results)

    print("\n=== 요약 ===")
    print(f"전체 {summary['total_cases']}건 / 에러 {summary['error_count']}건 (에러율 {summary['error_rate']:.2%})")
    print(f"담당부서 정확도       : {summary['department_accuracy']:.2%}")
    print(f"문의유형 정확도       : {summary['inquiry_type_accuracy']:.2%}")
    print(f"부서+유형 모두 정확도 : {summary['both_correct_accuracy']:.2%}")
    print(
        f"응답 지연(초) 평균/중앙값/최대/최소 : "
        f"{summary['latency_sec']['avg']}/{summary['latency_sec']['p50']}/"
        f"{summary['latency_sec']['max']}/{summary['latency_sec']['min']}"
    )
    print(f"토큰 사용량 합계/건당 평균 : {summary['tokens']['total_sum']}/{summary['tokens']['avg_per_case']}")
    print("\n부서별 정확도:")
    for dept, stat in summary["per_department"].items():
        print(
            f"  {dept:10s} 부서정확도 {stat['dept_correct']}/{stat['total']}  "
            f"유형정확도 {stat['type_correct']}/{stat['total']}"
        )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / f"classification_eval_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(
        json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n결과 저장: {out_path}")


if __name__ == "__main__":
    main()
