import { useState } from 'react'

// 실제 retrieve_node 결과(state.retrieved_docs)를 그대로 보여준다. 목업에 있던
// "문단 번호"/"최종 수정일"은 실제 API에 없는 값이라 제외했다.
function splitQuestionAnswer(content) {
  const marker = '\n답변: '
  const index = content.indexOf(marker)
  if (index === -1) return { question: null, answer: content }
  return {
    question: content.slice(0, index).replace(/^질문: /, ''),
    answer: content.slice(index + marker.length),
  }
}

// 문의를 새로 등록하거나 draft 화면에 갔다가 돌아오면 이 컴포넌트는 매번 새로
// 마운트되므로(App.jsx가 activeView !== 'rag'일 때 렌더 트리에서 아예 빼버림),
// useState 초기값을 currentSourceDocs 기준으로 한 번만 계산해두면 "지금 이 답변이
// 근거로 쓴 문서"가 자동으로 체크된 채로 화면이 열린다.
function initialSelection(docs, currentSourceDocs) {
  const sourceSet = new Set((currentSourceDocs || []).map((d) => d.source))
  const matched = docs.reduce((acc, doc, index) => {
    if (sourceSet.has(doc.source)) acc.push(index)
    return acc
  }, [])
  return new Set(matched.length ? matched : docs.length ? [0] : [])
}

export default function RagView({
  result,
  onNext,
  onPrev,
  onGenerateFromDocs,
  generating,
  generateError,
  currentSourceDocs,
}) {
  const docs = result?.retrieved_docs || []
  const [selected, setSelected] = useState(() => initialSelection(docs, currentSourceDocs))

  if (!result || !result.classification) {
    return (
      <div className="view" id="view-rag">
        <div className="card empty-state">
          아직 검색된 근거 문서가 없습니다.
          <br />
          '문의 접수' 화면에서 문의를 등록해 주세요.
        </div>
      </div>
    )
  }

  const toggle = (index) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(index)) next.delete(index)
      else next.add(index)
      return next
    })
  }

  const usedSources = new Set((currentSourceDocs || []).map((d) => d.source))
  const selectedDocs = docs.filter((_, index) => selected.has(index))

  return (
    <div className="view" id="view-rag">
      <h2 className="section-title">관련 근거 문서 (관련도 순)</h2>
      <p style={{ fontSize: 12.5, color: 'var(--text-dim)', marginTop: -8, marginBottom: 16 }}>
        답변 생성에 쓸 문서를 체크박스로 골라 "선택한 문서로 답변 생성"을 누르면, 그 문서(들)만
        근거로 답변 초안을 다시 만듭니다. 아무것도 고르지 않으면 기존 답변이 유지됩니다.
      </p>

      {docs.length === 0 && (
        <div className="card empty-state">이 문의와 관련해 검색된 근거 문서가 없습니다.</div>
      )}

      {docs.map((doc, index) => {
        const { question, answer } = splitQuestionAnswer(doc.content)
        return (
          <label
            className={`rag-item rag-item-selectable${selected.has(index) ? ' selected' : ''}`}
            key={`${doc.source}-${index}`}
          >
            <div className="rag-head">
              <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <input
                  type="checkbox"
                  checked={selected.has(index)}
                  onChange={() => toggle(index)}
                />
                <span className="rag-source">📄 {doc.source}</span>
                {usedSources.has(doc.source) && (
                  <span className="badge low">현재 답변 근거</span>
                )}
              </span>
              <span className="rag-score">유사도 {doc.score.toFixed(3)}</span>
            </div>
            {question && <div className="rag-body" style={{ fontWeight: 700, marginBottom: 4 }}>{question}</div>}
            <div className="rag-body">{answer}</div>
          </label>
        )
      })}

      {docs.length > 0 && (
        <div className="card" style={{ marginTop: 4, marginBottom: 4 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
            <span style={{ fontSize: 12.5, color: 'var(--text-dim)' }}>
              {selected.size}개 문서 선택됨
            </span>
            <button
              className="btn btn-teal"
              type="button"
              disabled={selected.size === 0 || generating}
              onClick={() => onGenerateFromDocs(selectedDocs)}
            >
              {generating ? '답변 생성 중...' : `선택한 문서로 답변 생성 (${selected.size}개)`}
            </button>
          </div>
          {generateError && (
            <div style={{ fontSize: 12, color: 'var(--red)', marginTop: 8 }}>
              답변 생성 실패: {generateError}
            </div>
          )}
        </div>
      )}

      <div className="form-actions">
        <button className="btn btn-ghost" type="button" onClick={onPrev}>
          ← 이전 단계: AI 분석 결과
        </button>
        <button className="btn btn-primary" type="button" onClick={onNext}>
          다음 단계: 답변 초안 편집 →
        </button>
      </div>
    </div>
  )
}
