from fastapi import APIRouter

from app.graph.nodes.rules import list_all_departments

router = APIRouter(prefix="/departments", tags=["departments"])


@router.get("")
def get_departments() -> list[str]:
    """rules.yaml에 정의된 담당부서 전체 목록. 담당자가 AI 분류 결과를 수동으로
    보정할 때 프론트엔드 버튼 선택지로 쓴다."""
    return list_all_departments()
