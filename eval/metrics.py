"""13-1절 평가지표 목표 수준. 개발 중 이 기준으로 파이프라인 결과를 검증한다."""

TARGETS = {
    "classification_f1": 0.80,       # 문의 분류 정확도 (Accuracy/F1)
    "dept_match_rate": 0.80,          # 담당 부서 추천 정답 일치율
    "rag_top3_precision": 0.75,       # RAG 검색 적합도 (Top-3)
    "answer_quality_score": 4.0,      # 답변 초안 품질 (담당자 평가, 5점 만점)
    "time_reduction_rate": 0.50,      # 수작업 대비 처리시간 단축률
}


def check_targets(results: dict) -> dict:
    """{지표명: 측정값} -> {지표명: 목표달성여부}"""
    return {
        metric: results.get(metric, 0) >= target
        for metric, target in TARGETS.items()
    }
