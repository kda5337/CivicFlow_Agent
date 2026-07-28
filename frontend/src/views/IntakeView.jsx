import { useState } from 'react'

// 실제 백엔드(POST /inquiries)에 연결된 화면. 백엔드는 text 한 필드만 받으므로
// 제목+내용을 합쳐서 보낸다. 연락처는 이를 받아줄 API가 없어 장식용으로만
// 남겨뒀다(제출 시 전송되지 않음).
export default function IntakeView({ onSubmit, loading, error }) {
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')

  const canSubmit = content.trim().length > 0 && !loading

  const handleSubmit = () => {
    if (!canSubmit) return
    const text = title.trim() ? `${title.trim()}\n\n${content.trim()}` : content.trim()
    onSubmit(text)
  }

  return (
    <div className="view" id="view-intake">
      {error && <div className="error-banner">요청 실패: {error}</div>}
      <div className="grid cols-2">
        <div className="card">
          <h2 className="section-title">문의 등록</h2>
          <label>문의 제목</label>
          <input
            type="text"
            placeholder="예: 수강신청 정정 시 오류 메시지가 나타납니다"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
          />
          <label>문의 내용</label>
          <textarea
            placeholder="문의 내용을 입력하세요"
            value={content}
            onChange={(event) => setContent(event.target.value)}
          />
          <label>연락처</label>
          <input type="text" placeholder="010-0000-0000" />
          <div className="form-actions">
            <button className="btn btn-ghost" type="button" disabled={loading}>
              임시저장
            </button>
            <button className="btn btn-primary" type="button" onClick={handleSubmit} disabled={!canSubmit}>
              {loading ? '분석 중...' : '등록하고 AI 분석 요청 →'}
            </button>
          </div>
        </div>
        <div className="card" style={{ background: 'var(--navy-900)', color: '#fff', height: 'fit-content' }}>
          <h2 className="section-title" style={{ color: '#fff' }}>등록 후 처리 흐름</h2>
          <div style={{ fontSize: 12.5, lineHeight: 2.2, color: 'rgba(255,255,255,.75)' }}>
            문의가 등록되면 <b style={{ color: '#59D6CF' }}>AI 분석 결과</b> 단계로 자동 전달되어
            유형·담당 부서·우선순위가 분류됩니다. 이후 관련 FAQ를{' '}
            <b style={{ color: '#59D6CF' }}>RAG 검색</b>으로 조회하고, 답변 초안이 자동 생성됩니다.
          </div>
        </div>
      </div>
    </div>
  )
}
