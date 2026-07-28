import { useEffect, useState } from 'react'

// 실제 generate_node 결과(state.draft_answer)를 편집 가능한 형태로 보여준다.
// "최종 답변으로 저장"은 이를 받아줄 백엔드 엔드포인트가 아직 없어 브라우저
// 안에서만 저장 상태를 표시한다(새로고침하면 사라짐) — 서버에 실제로 저장되는
// 것처럼 보이지 않도록 문구로 명시한다. "AI 재생성 요청"은 같은 원문으로
// 파이프라인을 다시 호출하는 실제 동작이다.
export default function DraftView({ result, onRegenerate, loading }) {
  const [draftText, setDraftText] = useState('')
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (result) {
      setDraftText(result.draft_answer || result.intake_reply || '')
      setSaved(false)
    }
  }, [result])

  if (!result) {
    return (
      <div className="view" id="view-draft">
        <div className="card empty-state">
          아직 생성된 답변 초안이 없습니다.
          <br />
          '문의 접수' 화면에서 문의를 등록해 주세요.
        </div>
      </div>
    )
  }

  // 민감 민원(9절 Rule)에 걸린 문의도 generate_node가 다른 문의와 똑같이 RAG 근거를
  // 반영한 답변 초안을 만든다(백엔드가 더 이상 건너뛰지 않음). status만으로는 이
  // 케이스를 구분할 수 없어(항상 pending_review), rule_flags.requires_manager_review로
  // 판단해 경고 배너 + 참고 근거 문서를 추가로 보여준다 — 다만 초안 자체는 다른
  // 문의와 동일하게 편집/재생성/저장이 모두 가능하다(담당자가 검토하며 고치는 게
  // 바로 이 화면의 목적이기 때문).
  const requiresReview = Boolean(result.rule_flags?.requires_manager_review)
  const docs = result.retrieved_docs || []
  const edited = draftText !== (result.draft_answer || result.intake_reply || '')

  return (
    <div className="view" id="view-draft">
      {requiresReview && (
        <div className="card" style={{ border: '1.5px solid var(--red)', marginBottom: 16 }}>
          <h2 className="section-title" style={{ color: 'var(--red)' }}>⚠ 관리자 즉시 검토 필요</h2>
          <p style={{ fontSize: 12.5, color: 'var(--text-dim)' }}>
            규칙 엔진이 이 문의를 즉시 관리자 검토가 필요한 사안으로 분류했습니다
            ({(result.rule_flags?.review_reasons || []).join(', ') || '민감 민원'}).
            아래 AI 답변 초안은 참고용이며, 내용을 검토·수정한 뒤에만 발송해 주세요.
          </p>
        </div>
      )}

      <div className="editor-wrap">
        <div className="card">
          <h2 className="section-title">AI 답변 초안</h2>
          <textarea
            style={{ minHeight: 220 }}
            value={draftText}
            onChange={(event) => {
              setDraftText(event.target.value)
              setSaved(false)
            }}
          />
          <div className="form-actions">
            <button className="btn btn-ghost" type="button" onClick={onRegenerate} disabled={loading}>
              {loading ? '재생성 중...' : 'AI 재생성 요청'}
            </button>
            <button className="btn btn-primary" type="button" onClick={() => setSaved(true)} disabled={saved}>
              {saved ? '저장됨 ✓' : '최종 답변으로 저장 ✓'}
            </button>
          </div>
        </div>
        <div className="card">
          <h2 className="section-title">수정 이력</h2>
          <div className="rev-item">
            <div className="rev-time">{result.status}</div>
            <div className="rev-actor">AI 초안 생성</div>
            <div style={{ color: 'var(--text-dim)' }}>
              근거 문서 {docs.length}건 기반 자동 생성
            </div>
          </div>
          {edited && (
            <div className="rev-item">
              <div className="rev-time">방금</div>
              <div className="rev-actor">담당자 편집 중</div>
              <div style={{ color: 'var(--text-dim)' }}>아직 저장되지 않음</div>
            </div>
          )}
          <div className="rev-item">
            <div className="rev-time">-</div>
            <div className="rev-actor" style={{ color: 'var(--text-dim)' }}>
              {saved ? '이 브라우저 세션에만 저장됨 (서버 저장 API 미구현)' : '최종 승인 대기 중'}
            </div>
          </div>
          {result.trace_url && (
            <div className="rev-item">
              <a href={result.trace_url} target="_blank" rel="noreferrer">
                Langfuse 트레이스 보기 →
              </a>
            </div>
          )}
        </div>
      </div>

      {requiresReview && docs.length > 0 && (
        <div className="card" style={{ marginTop: 16 }}>
          <h2 className="section-title">답변 근거로 쓰인 문서</h2>
          {docs.map((doc, index) => (
            <div className="rag-item" key={`${doc.source}-${index}`}>
              <div className="rag-head">
                <span className="rag-source">📄 {doc.source}</span>
                <span className="rag-score">유사도 {doc.score.toFixed(3)}</span>
              </div>
              <div className="rag-body">{doc.content}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
