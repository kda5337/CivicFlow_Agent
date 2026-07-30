"""문의 임베딩 유사도 캐시. chroma_merged_faq(원본 FAQ)와는 별도로, 이미 파이프라인이
처리한 문의의 최종 결과(분류/rule_flags/검색문서/답변초안)를 저장해 비슷한 재질문이
오면 전체 파이프라인(intake~generate)을 다시 돌리지 않고 재사용하기 위한 캐시다.

관리자검토가 필요했던 결과(rule_flags.requires_manager_review=true)는 저장하지 않는다
— 안전/법적 사안은 텍스트가 비슷해도 매번 사람 검토를 다시 거쳐야 하기 때문이다.
"""

import json

from app.rag.vectorstore import get_vectorstore

QUERY_CACHE_COLLECTION_NAME = "query_cache"

# 코사인 유사도 임계값. query_cache에 실제로 쌓인 70건을 대상으로 실측한 결과:
# 진짜 같은 의도의 재질문은 0.79~0.87, 같은 부서의 다른 이슈는 0.60, 무관한 질문은 0.30
# 수준으로 나뉘어서, 그 사이인 0.80을 기준으로 잡았다. 재현율보다 정밀도를 우선했다
# (애매하면 캐시를 안 쓰고 기존 파이프라인으로 넘기는 쪽이 안전하기 때문).
CACHE_SIMILARITY_THRESHOLD = 0.80


def lookup_cache_entry(raw_text: str, threshold: float = CACHE_SIMILARITY_THRESHOLD) -> dict | None:
    """raw_text와 가장 유사한 캐시 항목을 찾아 파이프라인 최종 결과 형태로 돌려준다.

    임계값 미만이거나 컬렉션이 비어있으면 None을 반환해 기존 파이프라인으로 넘어가게 한다.
    threshold를 지정하지 않으면 기본값(CACHE_SIMILARITY_THRESHOLD)을 쓴다 — 호출하는 쪽마다
    재사용을 더/덜 보수적으로 하고 싶을 때 개별적으로 올려 쓸 수 있게 하기 위함이다
    (예: 시민 접수 경로는 0.90으로 더 엄격하게 요구).
    """
    vectorstore = get_vectorstore(QUERY_CACHE_COLLECTION_NAME)
    results = vectorstore.similarity_search_with_relevance_scores(raw_text, k=1)
    if not results:
        return None

    doc, score = results[0]
    if score < threshold:
        return None

    meta = doc.metadata
    return {
        "classification": json.loads(meta["classification"]),
        "rule_flags": json.loads(meta["rule_flags"]),
        "retrieved_docs": json.loads(meta["retrieved_docs"]),
        "draft_answer": meta["draft_answer"],
        # sources는 이 필드가 생기기 전에 저장된 예전 캐시 항목엔 없을 수 있어 기본값을 둔다.
        "sources": json.loads(meta.get("sources", "[]")),
        "matched_question": doc.page_content,
        "score": score,
    }


def store_cache_entry(inquiry_id: str, raw_text: str, state: dict) -> bool:
    """파이프라인 실행 결과 state를 query_cache 컬렉션에 저장한다.

    관리자검토필요였던 결과는 저장을 건너뛰고 False를 반환한다.
    """
    rule_flags = state.get("rule_flags") or {}
    if rule_flags.get("requires_manager_review"):
        return False

    vectorstore = get_vectorstore(QUERY_CACHE_COLLECTION_NAME)
    vectorstore.add_texts(
        texts=[raw_text],
        metadatas=[
            {
                "classification": json.dumps(state.get("classification") or {}, ensure_ascii=False),
                "rule_flags": json.dumps(rule_flags, ensure_ascii=False),
                "retrieved_docs": json.dumps(state.get("retrieved_docs") or [], ensure_ascii=False),
                "draft_answer": state.get("draft_answer") or "",
                "sources": json.dumps(state.get("sources") or [], ensure_ascii=False),
                "created_at": state.get("received_at") or "",
            }
        ],
        ids=[inquiry_id],
    )
    return True
