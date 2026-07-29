// 각 화면의 메타데이터(사이드바 라벨/번호, 상단바 제목, 파이프라인 단계 매핑)를
// 한곳에 모아둔다 — Sidebar/Topbar/Pipeline이 이 목록만 보고 렌더링한다.
// 담당자가 직접 문의를 입력하던 "문의 접수"는 더 이상 쓰지 않는다 — 이제 모든 문의는
// 시민용 접수 페이지(/submit)를 통해서만 들어오고, 담당자는 "문의 접수함"에서 그 내역을
// 확인하고 "AI 처리 →"로 넘어간다.
export const VIEWS = [
  { key: 'dashboard', label: '대시보드', num: '01', group: '모니터링' },
  { key: 'submissions', label: '문의 접수함', num: '02', group: '모니터링' },
  { key: 'answered', label: '답변 완료함', num: '03', group: '모니터링' },
  { key: 'analysis', label: 'AI 분석 결과', num: '04', group: '문의 처리' },
  { key: 'rag', label: 'RAG 검색 결과', num: '05', group: '문의 처리' },
  { key: 'draft', label: '답변 초안 편집', num: '06', group: '문의 처리' },
  { key: 'review', label: '검토 완료', num: '07', group: '문의 처리' },
  { key: 'kb', label: '지식베이스 관리', num: '08', group: '지식 관리' },
]

export const VIEW_TITLES = Object.fromEntries(VIEWS.map((v) => [v.key, v.label]))

// 문의 처리 파이프라인(분류→근거탐색→답변생성→검토)에서 각 화면이 몇 번째
// 단계에 해당하는지. "접수"는 시민용 페이지에서 이미 끝난 단계라 여기엔 없다.
// 대시보드/문의 접수함/답변 완료함/지식베이스관리는 파이프라인과 무관해 -1.
export const PIPELINE_STEPS = ['분류', '근거탐색', '답변생성', '검토']
export const VIEW_STEP_MAP = {
  dashboard: -1,
  submissions: -1,
  answered: -1,
  analysis: 0,
  rag: 1,
  draft: 2,
  review: 3,
  kb: -1,
}

// 문의 처리 화면들을 순서대로 두어, "다음 단계"/"이전 단계" 버튼이 항상 정확한
// 화면으로 이동하게 한다(review가 마지막이라 다음 단계가 없고, analysis가 처음이라
// 이전 단계가 없음 -> 각각 null). 답변 초안을 다 고친 뒤 "검토하기"를 누르면 draft->
// review로 넘어가고, 실제 저장(등록)은 review 화면의 "검토 완료 & 등록" 버튼이 한다.
const PIPELINE_VIEW_ORDER = ['analysis', 'rag', 'draft', 'review']
export function nextPipelineView(currentKey) {
  const index = PIPELINE_VIEW_ORDER.indexOf(currentKey)
  if (index === -1 || index === PIPELINE_VIEW_ORDER.length - 1) return null
  return PIPELINE_VIEW_ORDER[index + 1]
}

export function previousPipelineView(currentKey) {
  const index = PIPELINE_VIEW_ORDER.indexOf(currentKey)
  if (index <= 0) return null
  return PIPELINE_VIEW_ORDER[index - 1]
}
