import { useEffect, useState } from 'react'
import { priorityBadgeClass } from '../priorityBadge.js'

// 파이프라인의 마지막 단계. 답변 초안 편집에서 담당자가 다 고친 텍스트(reviewText)를
// 읽기 전용으로 다시 한번 보여주고("검토"), "검토 완료 & 등록"을 눌러야 실제로
// 저장된다 — 이 문의가 사용자용 접수 페이지(/submit)에서 온 것이면
// (isLinkedToSubmission) PATCH /submissions/{id}/answer로 citizen_submissions에 실제
// 반영되어 사용자의 "답변 확인" 탭에 그대로 뜬다. 담당자가 '문의 접수'에서 직접 입력한
// 문의는 연결된 접수 건이 없어 등록해도 서버에 남지 않는다는 점을 화면에 그대로 알린다.
//
// onTestComplete가 있으면(관리자 테스트 섹션에서 온 흐름) 등록 완료 표시를 잠깐 보여준
// 뒤 자동으로 문의 접수함으로 돌아간다 — 테스트는 어차피 서버에 안 남으므로, 이 화면에
// 계속 머무를 이유가 없다.
export default function ReviewView({ result, reviewText, sources, onPrev, onFinalize, isLinkedToSubmission, onTestComplete }) {
  const [registering, setRegistering] = useState(false)
  const [registered, setRegistered] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!registered || isLinkedToSubmission || !onTestComplete) return
    const timer = setTimeout(onTestComplete, 1500)
    return () => clearTimeout(timer)
  }, [registered, isLinkedToSubmission, onTestComplete])

  if (!result) {
    return (
      <div className="view" id="view-review">
        <div className="card empty-state">
          아직 검토할 답변이 없습니다.
          <br />
          '문의 접수' 화면에서 문의를 등록해 주세요.
        </div>
      </div>
    )
  }

  const classification = result.classification || {}
  const finalText = reviewText ?? result.draft_answer ?? ''

  const handleRegister = async () => {
    setError(null)
    setRegistering(true)
    try {
      if (isLinkedToSubmission) {
        await onFinalize(finalText)
      }
      setRegistered(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setRegistering(false)
    }
  }

  return (
    <div className="view" id="view-review">
      <div className="grid cols-2">
        <div className="card">
          <h2 className="section-title">최종 답변 (읽기 전용)</h2>
          <div style={{ fontSize: 15.5, lineHeight: 1.8, whiteSpace: 'pre-wrap', color: 'var(--text)' }}>{finalText}</div>
          {sources && sources.length > 0 && (
            <div className="sources-readonly">
              <div className="sources-readonly-label">참고 자료</div>
              <ul>
                {sources.map((label) => (
                  <li key={label}>{label}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <div className="card">
          <h2 className="section-title">최종 확인</h2>
          <div className="result-row">
            <span className="result-key">문의 유형</span>
            <span className="result-val">{classification.문의유형}</span>
          </div>
          <div className="result-row">
            <span className="result-key">담당 부서</span>
            <span className="result-val">{classification.담당부서}</span>
          </div>
          <div className="result-row">
            <span className="result-key">우선순위</span>
            <span className={`badge ${priorityBadgeClass(classification.우선순위)}`}>{classification.우선순위}</span>
          </div>

          <div style={{ fontSize: 12.5, color: 'var(--text-dim)', margin: '18px 0 6px' }}>문의 원문</div>
          <div style={{ fontSize: 13, lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>{result.raw_text}</div>
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        {registered ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '8px 0' }}>
            <span className="badge low" style={{ fontSize: 16, padding: '10px 18px', fontWeight: 700 }}>
              등록 완료 ✓
            </span>
            <span style={{ fontSize: 15, color: 'var(--text)', fontWeight: 500 }}>
              {isLinkedToSubmission
                ? '사용자 문의 접수 건에 최종 답변이 저장됐습니다 (사용자의 "답변 확인" 탭에 표시됨).'
                : onTestComplete
                  ? '테스트 실행이라 서버에는 저장되지 않았습니다. 잠시 후 문의 접수함으로 이동합니다...'
                  : '이 문의는 사용자 접수 건과 연결되지 않아 서버에는 저장되지 않았습니다.'}
            </span>
          </div>
        ) : (
          <>
            {error && <div className="error-banner">등록 실패: {error}</div>}
            <p style={{ fontSize: 12.5, color: 'var(--text-dim)', margin: '0 0 14px' }}>
              위 내용을 최종 확인했다면 등록하세요. 등록 후에는 이 화면에서 다시 수정할 수 없습니다 — 고칠 내용이 있으면
              "이전 단계"로 돌아가 답변 초안을 다시 편집해 주세요.
            </p>
            <div className="form-actions" style={{ justifyContent: 'flex-start' }}>
              <button className="btn btn-ghost" type="button" onClick={onPrev}>
                ← 이전 단계: 답변 초안 편집
              </button>
              <button
                className="btn btn-primary"
                type="button"
                onClick={handleRegister}
                disabled={registering}
                style={{ fontSize: 16, padding: '16px 32px', fontWeight: 700 }}
              >
                {registering ? '등록 중...' : '검토 완료 & 등록'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
