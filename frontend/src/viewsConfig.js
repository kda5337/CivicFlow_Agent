// 여섯 개 화면의 메타데이터(사이드바 라벨/번호, 상단바 제목, 파이프라인 단계 매핑)를
// 한곳에 모아둔다 — Sidebar/Topbar/Pipeline이 이 목록만 보고 렌더링한다.
export const VIEWS = [
  { key: 'dashboard', label: '대시보드', num: '01', group: '모니터링' },
  { key: 'intake', label: '문의 접수', num: '02', group: '문의 처리' },
  { key: 'analysis', label: 'AI 분석 결과', num: '03', group: '문의 처리' },
  { key: 'rag', label: 'RAG 검색 결과', num: '04', group: '문의 처리' },
  { key: 'draft', label: '답변 초안 편집', num: '05', group: '문의 처리' },
  { key: 'kb', label: '지식베이스 관리', num: '06', group: '지식 관리' },
]

export const VIEW_TITLES = Object.fromEntries(VIEWS.map((v) => [v.key, v.label]))

// 문의 처리 파이프라인(접수→분류→근거탐색→답변생성→검토)에서 각 화면이 몇 번째
// 단계에 해당하는지. 대시보드/지식베이스관리는 파이프라인과 무관해 -1.
export const PIPELINE_STEPS = ['접수', '분류', '근거탐색', '답변생성', '검토']
export const VIEW_STEP_MAP = {
  dashboard: -1,
  intake: 0,
  analysis: 1,
  rag: 2,
  draft: 3,
  kb: -1,
}

// 문의 처리 화면들을 순서대로 두어, "다음 단계" 버튼이 항상 정확한 다음 화면으로
// 이동하게 한다(draft가 마지막이라 다음 단계가 없음 -> null).
const PIPELINE_VIEW_ORDER = ['intake', 'analysis', 'rag', 'draft']
export function nextPipelineView(currentKey) {
  const index = PIPELINE_VIEW_ORDER.indexOf(currentKey)
  if (index === -1 || index === PIPELINE_VIEW_ORDER.length - 1) return null
  return PIPELINE_VIEW_ORDER[index + 1]
}
