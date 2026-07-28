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

export default function RagView({ result, onNext }) {
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

  const docs = result.retrieved_docs || []

  return (
    <div className="view" id="view-rag">
      <h2 className="section-title">관련 근거 문서 (관련도 순)</h2>

      {docs.length === 0 && (
        <div className="card empty-state">이 문의와 관련해 검색된 근거 문서가 없습니다.</div>
      )}

      {docs.map((doc, index) => {
        const { question, answer } = splitQuestionAnswer(doc.content)
        return (
          <div className="rag-item" key={`${doc.source}-${index}`}>
            <div className="rag-head">
              <span className="rag-source">📄 {doc.source}</span>
              <span className="rag-score">유사도 {doc.score.toFixed(3)}</span>
            </div>
            {question && <div className="rag-body" style={{ fontWeight: 700, marginBottom: 4 }}>{question}</div>}
            <div className="rag-body">{answer}</div>
          </div>
        )
      })}

      <div className="form-actions">
        <button className="btn btn-primary" type="button" onClick={onNext}>
          다음 단계: 답변 초안 편집 →
        </button>
      </div>
    </div>
  )
}
