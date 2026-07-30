from functools import lru_cache
from pathlib import Path

import yaml

from app.core.tracing import get_langfuse_client
from app.graph.state import InquiryState

RULES_PATH = Path(__file__).resolve().parents[3] / "rules.yaml"

# 우선순위 값끼리 동시에 매칭됐을 때 승자를 가리는 순위(담당부서는 규칙별 priority 필드로 가린다).
_PRIORITY_RANK = {"낮음": 0, "보통": 1, "높음": 2, "최상": 3}


@lru_cache
def _load_rules() -> list[dict]:
    with open(RULES_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)["rules"]


def list_all_departments() -> list[str]:
    """rules.yaml의 담당부서 규칙들이 가리키는 부서명을 전부 모아 정렬해서 돌려준다.

    담당자가 AI 분류 결과의 담당부서가 틀렸다고 판단했을 때, 화면에서 고를 수 있는
    선택지 전체를 rules.yaml 하나로만 관리하기 위한 용도(프론트에서 하드코딩하지 않음).
    """
    departments = {
        rule["result"]["담당부서"]
        for rule in _load_rules()
        if "담당부서" in rule.get("result", {})
    }
    return sorted(departments)


def rules_node(state: InquiryState) -> dict:
    """9절: Rule 엔진 노드. classification.주요문의유형으로 규칙 후보군을 좁힌 뒤,
    키워드 매칭으로 담당부서/우선순위를 보정한다.

    classify_node는 문의 하나가 여러 유형에 해당할 수 있어 문의유형들(전체 후보)과
    주요문의유형(대표 유형 하나)을 함께 내놓는데, 이 노드는 여전히 주요문의유형
    하나만 보고 라우팅한다 — 여러 후보 중 무엇이 대표인지는 이미 classify_node에서
    LLM이 정한 뒤라, rules_node 로직 자체는 문의유형이 단일 값이던 때와 동일하다.
    최종 출력에서는 하위 호환을 위해 주요문의유형을 문의유형 키로 옮겨 담는다.

    - 담당부서/우선순위는 LLM(classify_node)이 정하지 않는다 — 여기서 rules.yaml만으로
      처음부터 결정한다. 문의유형마다 keywords 없는 기본(fallback) 규칙이 하나씩 있어서
      다른 규칙이 하나도 안 걸려도 담당부서/우선순위가 비는 일은 없다.
    - 담당부서 규칙은 applies_to(대상 문의유형)로 후보가 좁혀지고, 동시에 여러 규칙이
      매칭되면 규칙의 priority 값이 가장 높은 것이 채택된다. fallback 규칙은
      priority: -1로 가장 낮게 두어, 구체적인 규칙이 하나라도 걸리면 항상 밀려난다.
    - 우선순위 규칙은 문의유형과 무관하게(applies_to 없이) 항상 검사되며, 여러 값이
      동시에 매칭되면 낮음<보통<높음<최상 순위가 가장 높은 값이 채택된다. 규칙에 명시적
      priority가 있으면 그 값을 랭킹으로 쓰고(fallback의 priority: -1이 그 예), 없으면
      우선순위 값 자체의 등급(_PRIORITY_RANK)을 랭킹으로 쓴다 — 그래야 "단순조회_낮음"
      같은 하향 규칙이 fallback의 '보통'보다 밀리지 않는다.
    - 겹쳤던 담당부서 후보 전체는 rule_flags.candidate_departments로 별도 보존해,
      왜 이 부서로 결정됐는지 나중에 추적할 수 있게 한다.

    LLM 호출이 아니지만 분류 결과를 실제로 바꾸는 결정 지점이므로,
    'tool' 타입 span으로 명시해 무엇이 왜 바뀌었는지 트레이스에서 바로 보이게 한다.
    """
    text = state["raw_text"]
    before = dict(state.get("classification") or {})
    문의유형 = before.get("주요문의유형")

    with get_langfuse_client().start_as_current_observation(
        name="apply-rules",
        as_type="tool",
        input={"classification_before": before},
    ) as span:
        classification = dict(before)
        classification["문의유형"] = classification.pop("주요문의유형", None)
        matched_rules: list[str] = []
        requires_manager_review = False
        review_reasons: list[str] = []  # 관리자검토필요를 실제로 세팅한 규칙 이름만 모음
        dept_candidates: list[tuple[int, str]] = []  # (priority, 담당부서)
        priority_candidates: list[tuple[int, str]] = []  # (rank, 우선순위)

        for rule in _load_rules():
            scope = rule.get("applies_to")
            if scope and 문의유형 not in scope:
                continue
            keywords = rule.get("keywords") or []
            if keywords and not any(keyword in text for keyword in keywords):
                continue  # keywords가 비어있으면(fallback 규칙) 항상 매칭으로 간주한다.

            matched_rules.append(rule["name"])
            result = rule.get("result", {})

            for field, value in result.items():
                if field == "담당부서":
                    dept_candidates.append((rule.get("priority", 0), value))
                elif field == "우선순위":
                    rank = rule["priority"] if "priority" in rule else _PRIORITY_RANK.get(value, 0)
                    priority_candidates.append((rank, value))
                elif field == "관리자검토필요" and value:
                    requires_manager_review = True
                    review_reasons.append(rule["name"])

        # 서로 다른 규칙이 같은 부서를 가리킨 경우까지 중복으로 남기면 실제로는 경합이
        # 없었는데도 후보가 여러 개인 것처럼 보이므로, 값 기준으로 중복을 제거한다.
        candidate_departments = list(dict.fromkeys(dept for _, dept in dept_candidates))
        if dept_candidates:
            classification["담당부서"] = max(dept_candidates, key=lambda c: c[0])[1]
        if priority_candidates:
            classification["우선순위"] = max(priority_candidates, key=lambda c: c[0])[1]

        span.update(
            output={
                "matched_rules": matched_rules,
                "candidate_departments": candidate_departments,
                "classification_after": classification,
                "requires_manager_review": requires_manager_review,
                "review_reasons": review_reasons,
            }
        )

    return {
        "classification": classification,
        "rule_flags": {
            "matched_rules": matched_rules,
            "candidate_departments": candidate_departments,
            "requires_manager_review": requires_manager_review,
            "review_reasons": review_reasons,
        },
    }