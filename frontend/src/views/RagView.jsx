import { useState } from 'react'

// retrieve_node의 유사도(score)는 높을수록 더 유사하다(0~1). 이 값을 넘는 문서가
// 하나도 없으면, 근거가 약한 채로 답변이 만들어질 수 있으니 담당자가 직접 확인하라는
// 경고를 보여준다.
const SIMILARITY_WARNING_THRESHOLD = 0.6

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
  onStartBlankDraft,
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
  const hasStrongMatch = docs.some((doc) => doc.score >= SIMILARITY_WARNING_THRESHOLD)

  // 문서를 2개 이상 골라두고 "선택한 문서로 답변 생성"을 누르지 않은 채 다음 단계로
  // 넘어가면, 답변 초안은 여전히 이전 근거(보통 1개)로 만든 것이라 화면의 체크 상태와
  // 실제 답변 내용이 어긋난다. 지금 고른 문서 조합이 실제로 답변에 반영된 것과 같을
  // 때만(=재생성을 거쳤을 때만) "다음 단계"를 허용한다.
  const selectedSources = new Set(selectedDocs.map((doc) => doc.source))
  const selectionMatchesDraft =
    selectedSources.size === usedSources.size && [...selectedSources].every((s) => usedSources.has(s))
  const blockNext = selected.size >= 2 && !selectionMatchesDraft

  return (
    <div className="view" id="view-rag">
      <h2 className="section-title">관련 근거 문서 (관련도 순)</h2>
      <p style={{ fontSize: 12.5, color: 'var(--text-dim)', marginTop: -8, marginBottom: 16 }}>
        답변 생성에 쓸 문서를 체크박스로 골라 "선택한 문서로 답변 생성"을 누르면, 그 문서(들)만
        근거로 답변 초안을 다시 만듭니다. 아무것도 고르지 않으면 기존 답변이 유지됩니다.
      </p>

      {docs.length > 0 && !hasStrongMatch && (
        <div className="warning-banner" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
          <span>
            ⚠ 유사도 {Math.round(SIMILARITY_WARNING_THRESHOLD * 100)}% 이상 비슷한 문서를 찾지 못했습니다. 근거가 약할 수
            있으니 답변 내용을 담당자가 각별히 주의해서 확인해 주세요.
          </span>
          {onStartBlankDraft && (
            <button className="btn btn-ghost" type="button" onClick={onStartBlankDraft}>
              근거 없이 빈 화면에서 직접 작성 →
            </button>
          )}
        </div>
      )}

      {docs.length === 0 && (
        <div className="card empty-state" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
          이 문의와 관련해 검색된 근거 문서가 없습니다.
          {onStartBlankDraft && (
            <button className="btn btn-ghost" type="button" onClick={onStartBlankDraft}>
              근거 없이 빈 화면에서 직접 작성 →
            </button>
          )}
        </div>
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
              <span className="rag-score">유사도: {(doc.score * 100).toFixed(1)}%</span>
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

      {blockNext && (
        <div className="warning-banner">
          ⚠ 문서를 2개 이상 선택했습니다. "선택한 문서로 답변 생성"을 먼저 눌러 답변에
          반영한 뒤에 다음 단계로 진행해 주세요.
        </div>
      )}

      <div className="form-actions">
        <button className="btn btn-ghost" type="button" onClick={onPrev}>
          ← 이전 단계: AI 분석 결과
        </button>
        <button className="btn btn-primary" type="button" onClick={onNext} disabled={blockNext}>
          다음 단계: 답변 초안 편집 →
        </button>
      </div>
    </div>
  )
}
