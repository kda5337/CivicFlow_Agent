from fastapi import APIRouter, HTTPException

from app.models.schemas import KnowledgeBaseItem, KnowledgeBaseItemWrite, KnowledgeBaseSource
from app.rag.knowledge_base import (
    FAQ_TABLES,
    KnowledgeBaseItemNotFound,
    create_item,
    delete_item,
    get_source_items,
    get_source_summaries,
    reprocess_source,
    update_item,
)

router = APIRouter(prefix="/knowledge-base", tags=["knowledge-base"])


def _check_table(table: str) -> None:
    if table not in FAQ_TABLES:
        raise HTTPException(status_code=404, detail="알 수 없는 지식베이스 출처입니다")


@router.get("", response_model=list[KnowledgeBaseSource])
def list_sources() -> list[KnowledgeBaseSource]:
    """지식베이스 관리 화면: 출처 테이블마다 Supabase 실제 건수 vs Chroma 임베딩
    건수를 나란히 보여준다. 두 값이 다르면 재처리가 필요하다는 뜻이다."""
    return get_source_summaries()


@router.get("/{table}/items", response_model=list[KnowledgeBaseItem])
def list_items(table: str) -> list[KnowledgeBaseItem]:
    """한 출처를 펼쳤을 때 보여줄 실제 질문/답변 전체 목록."""
    _check_table(table)
    return get_source_items(table)


@router.post("/{table}/items", response_model=KnowledgeBaseItem, status_code=201)
def add_item(table: str, payload: KnowledgeBaseItemWrite) -> KnowledgeBaseItem:
    """새 FAQ 항목을 추가하고 그 질문만 바로 임베딩한다(테이블 전체 재처리 불필요)."""
    _check_table(table)
    return create_item(table, payload.question, payload.answer)


@router.patch("/{table}/items/{item_id}", response_model=KnowledgeBaseItem)
def edit_item(table: str, item_id: int, payload: KnowledgeBaseItemWrite) -> KnowledgeBaseItem:
    """기존 항목을 덮어쓰고(이전 값은 남기지 않음) 임베딩도 새 질문으로 다시 만든다."""
    _check_table(table)
    try:
        return update_item(table, item_id, payload.question, payload.answer)
    except KnowledgeBaseItemNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.delete("/{table}/items/{item_id}", status_code=204)
def remove_item(table: str, item_id: int) -> None:
    """항목을 삭제하고 그 임베딩도 함께 지운다."""
    _check_table(table)
    try:
        delete_item(table, item_id)
    except KnowledgeBaseItemNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/{table}/reprocess", response_model=KnowledgeBaseSource)
def reprocess(table: str) -> KnowledgeBaseSource:
    """한 출처의 기존 임베딩을 지우고 Supabase 현재 데이터로 다시 만든다."""
    _check_table(table)
    return reprocess_source(table)
