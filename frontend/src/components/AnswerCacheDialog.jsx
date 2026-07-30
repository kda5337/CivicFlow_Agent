// 담당자가 "AI 처리 →"를 눌렀을 때 answer_cache 히트가 있으면 뜨는 확인 팝업.
// useInquiryPipeline.js의 pendingCacheDecision이 채워지면 나타나고, "이 답변 사용"/
// "새로 생성" 중 하나를 고르면 resolveCacheDecision(useCache)로 이어진다. x 버튼이나
// 바깥 배경을 클릭하면 onClose(dismissCacheDecision)가 불려 아무 선택도 하지 않고
// "AI 처리" 시도 자체가 취소된다(문의 접수함에 그대로 남음).
export default function AnswerCacheDialog({ pending, onResolve, onClose }) {
  if (!pending) return null

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0, 0, 0, 0.45)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        padding: 20,
      }}
      onClick={onClose}
    >
      <div
        className="card"
        style={{ maxWidth: 560, width: '100%', maxHeight: '80vh', overflowY: 'auto', position: 'relative' }}
        onClick={(event) => event.stopPropagation()}
      >
        <button
          type="button"
          onClick={onClose}
          aria-label="닫기"
          style={{
            position: 'absolute',
            top: 12,
            right: 12,
            background: 'none',
            border: 'none',
            fontSize: 18,
            lineHeight: 1,
            cursor: 'pointer',
            color: 'var(--text-dim)',
            padding: 4,
          }}
        >
          ✕
        </button>

        <h2 className="section-title" style={{ marginTop: 0, paddingRight: 24 }}>
          비슷한 문의에 이미 승인된 답변이 있습니다
        </h2>
        <p style={{ fontSize: 12.5, color: 'var(--text-dim)', marginTop: -8, marginBottom: 16 }}>
          이 답변을 그대로 초안으로 쓸까요? RAG 검색을 새로 하지 않고, 아래 출처를 그대로
          답변 초안 화면에 표시합니다. "새로 생성"을 고르면 기존처럼 RAG 검색부터 다시 진행합니다.
        </p>

        <div
          style={{
            background: 'var(--bg)',
            border: '1px solid var(--line)',
            borderRadius: 9,
            padding: 12,
            fontSize: 13,
            lineHeight: 1.6,
            whiteSpace: 'pre-wrap',
            marginBottom: 12,
          }}
        >
          {pending.finalAnswer}
        </div>

        <div style={{ fontSize: 12, color: 'var(--text-dim)', marginBottom: 20 }}>
          출처: {pending.sources.length > 0 ? pending.sources.join(', ') : '없음'}
        </div>

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button className="btn btn-ghost" type="button" onClick={() => onResolve(false)}>
            새로 생성
          </button>
          <button className="btn btn-teal" type="button" onClick={() => onResolve(true)}>
            이 답변 사용
          </button>
        </div>
      </div>
    </div>
  )
}
