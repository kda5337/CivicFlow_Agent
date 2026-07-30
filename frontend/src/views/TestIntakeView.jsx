import { useState } from 'react'

// 관리자 전용 테스트 섹션. 문의 원문만 입력해 전체 LangGraph 파이프라인
// (check_cache→intake→classify→apply_rules→retrieve→generate→store_cache)을 그대로
// 실행해본다. is_test 플래그가 캐시 조회/저장만 건너뛰게 하고, 나머지 LLM/RAG 호출은
// 실제 처리와 동일하게 전부 태운다. citizen_submissions에는 submission_id가 없어
// 원래도 기록되지 않고("문의 접수" 삭제 이전부터 그랬던 동작), 검토 완료 화면도
// isLinkedToSubmission=false라 실제 등록 없이 문의 접수함으로 자동 이동한다.
export default function TestIntakeView({ onSubmit, loading, error }) {
  const [text, setText] = useState('')

  const handleSubmit = () => {
    if (!text.trim()) return
    onSubmit(text.trim())
  }

  return (
    <div className="view" id="view-test">
      <div className="card">
        <h2 className="section-title">테스트 문의 등록</h2>
        <p style={{ fontSize: 12.5, color: 'var(--text-dim)', marginTop: -6, marginBottom: 16 }}>
          여기서 실행한 문의는 문의 접수함이나 캐시에 저장되지 않습니다. 전체 파이프라인(분류 →
          규칙보정 → RAG → 답변생성)을 그대로 테스트해보는 용도입니다. 마지막 "검토 완료" 화면에서
          등록을 눌러도 실제로 저장되지 않고, 문의 접수함으로 자동으로 돌아갑니다.
        </p>
        <textarea
          style={{ minHeight: 160 }}
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder="테스트로 돌려볼 문의 내용을 입력하세요."
        />
        {error && (
          <div className="error-banner" style={{ marginTop: 12 }}>
            처리 실패: {error}
          </div>
        )}
        <div className="form-actions">
          <button
            className="btn btn-primary"
            type="button"
            onClick={handleSubmit}
            disabled={loading || !text.trim()}
          >
            {loading ? '실행 중...' : '테스트 실행 →'}
          </button>
        </div>
      </div>
    </div>
  )
}
