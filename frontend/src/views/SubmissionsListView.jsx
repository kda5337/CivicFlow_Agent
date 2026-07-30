import { useEffect, useState } from 'react'
import { statusBadgeClass } from '../statusBadge.js'
import { isDelayed } from '../delay.js'
import DepartmentFilter, { ALL_DEPARTMENTS } from '../components/DepartmentFilter.jsx'
import { API_BASE_URL } from '../config.js'

const SUBMISSIONS_URL = `${API_BASE_URL}/submissions`

// 담당자가 사용자용 접수 페이지(/submit)로 들어온 문의를 조회하는 내부 화면.
// 접수 직후 서버가 바로 classify_node+rules_node를 돌려두므로, 목록에 문의유형/
// 담당부서/상태가 이미 채워져 있다("검토중"). "AI 처리 →"는 그 위에서 RAG 검색+
// 답변 초안까지 만드는 전체 파이프라인을 실행하고("답변 초안 편집" 화면까지 이동),
// 이 화면과 연결된 원본 접수 건(item.id)도 함께 넘겨서 최종 결과가 다시 이 레코드에
// 반영되게 한다(App.jsx의 linkedSubmissionId).
// lockDepartment: 담당자용 페이지(StaffView)에서 넘겨주면, 그 부서로 고정하고 부서
// 선택 칩 자체를 숨긴다(다른 부서로 바꿀 수 없게) — 관리자용 화면에서는 넘기지 않아
// 기존처럼 "전체"를 포함한 자유 선택 그대로 동작한다.
export default function SubmissionsListView({ onProcess, loading, processingSubmissionId, processError, lockDepartment }) {
  const [submissions, setSubmissions] = useState(null)
  const [error, setError] = useState(null)
  const [deptFilter, setDeptFilter] = useState(ALL_DEPARTMENTS)
  const effectiveDeptFilter = lockDepartment || deptFilter

  const load = () => {
    setError(null)
    fetch(SUBMISSIONS_URL)
      .then((response) => {
        if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
        return response.json()
      })
      // 답변완료 건은 더 이상 처리할 일이 없는 건이라 이 접수함에서는 빼고, "답변 완료함"
      // (AnsweredView)에서만 보이게 한다. 남은 건 중 rules.yaml 9절 민감 민원 규칙에 걸려
      // 담당자 즉시 검토가 필요한 건(requires_manager_review)을 맨 위로 올리고, 그다음으로
      // 지연 건(익일 오전 9시 초과 미답변)을 올린다 — 관리자 검토 필요보다는 항상 아래.
      // 같은 그룹 안에서는 서버가 이미 내려준 최신 접수순을 그대로 유지한다(Array.sort는
      // 안정 정렬).
      .then((data) =>
        setSubmissions(
          data
            .filter((item) => item.status !== '답변완료')
            .sort((a, b) => {
              const reviewDiff = Number(b.requires_manager_review) - Number(a.requires_manager_review)
              if (reviewDiff !== 0) return reviewDiff
              return Number(isDelayed(b.submitted_at)) - Number(isDelayed(a.submitted_at))
            })
        )
      )
      .catch((err) => setError(err.message))
  }

  useEffect(() => {
    load()
  }, [])

  const visibleSubmissions = submissions
    ? submissions.filter((item) => effectiveDeptFilter === ALL_DEPARTMENTS || item.department === effectiveDeptFilter)
    : null

  return (
    <div className="view" id="view-submissions">
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <h2 className="section-title" style={{ margin: 0 }}>
            문의 접수함 {visibleSubmissions ? `(${visibleSubmissions.length}건)` : ''}
          </h2>
          <button className="btn btn-ghost" type="button" onClick={load}>
            새로고침
          </button>
        </div>

        {!lockDepartment && <DepartmentFilter value={deptFilter} onChange={setDeptFilter} />}

        {error && <div className="error-banner">목록을 불러오지 못했습니다: {error}</div>}
        {processError && <div className="error-banner">AI 처리에 실패했습니다: {processError}</div>}

        {visibleSubmissions && visibleSubmissions.length === 0 && (
          <div className="empty-state">
            {effectiveDeptFilter === ALL_DEPARTMENTS ? (
              <>
                처리 대기 중인 문의가 없습니다.
                <br />
                답변을 완료한 문의는 사이드바의 "답변 완료함"에서 확인할 수 있습니다.
              </>
            ) : (
              `'${effectiveDeptFilter}' 담당의 처리 대기 중인 문의가 없습니다.`
            )}
          </div>
        )}

        {visibleSubmissions && visibleSubmissions.length > 0 && (
          <table>
            <tbody>
              <tr>
                <th></th>
                <th>접수 시각</th>
                <th>이름</th>
                <th>연락처</th>
                <th>문의 내용</th>
                <th>자동 분류</th>
                <th>상태</th>
                <th></th>
              </tr>
              {visibleSubmissions.map((item) => {
                // 관리자 검토 필요(빨간색)가 최우선 표시다. 지연(주황색)은 관리자 검토가
                // 걸리지 않은 건에만 보여줘서 두 색이 같은 행에서 겹치지 않게 한다 —
                // 정렬 순서도 관리자 검토 필요 > 지연 순이라 이 조건과 항상 일치한다.
                const delayed = !item.requires_manager_review && isDelayed(item.submitted_at)
                return (
                <tr
                  key={item.id}
                  style={
                    item.requires_manager_review
                      ? { background: 'var(--red-soft)', boxShadow: 'inset 3px 0 0 var(--red)' }
                      : delayed
                        ? { background: 'var(--amber-soft)', boxShadow: 'inset 3px 0 0 var(--amber)' }
                        : undefined
                  }
                >
                  <td>
                    {item.requires_manager_review ? (
                      <span className="badge high" title="rules.yaml 민감 민원 규칙에 걸려 즉시 검토가 필요합니다">
                        ⚠ 검토 필요
                      </span>
                    ) : delayed ? (
                      <span className="badge mid" title="접수 익일 오전 9시까지 미답변으로 지연 처리되었습니다">
                        ⏰ 지연
                      </span>
                    ) : null}
                  </td>
                  <td className="mono" style={{ whiteSpace: 'nowrap' }}>
                    {new Date(item.submitted_at).toLocaleString('ko-KR')}
                  </td>
                  <td>{item.name}</td>
                  <td className="mono">{item.contact}</td>
                  <td style={{ maxWidth: 320 }}>{item.raw_text}</td>
                  <td style={{ whiteSpace: 'nowrap' }}>
                    {item.inquiry_type ? (
                      <>
                        {item.inquiry_type}
                        <br />
                        <span style={{ color: 'var(--text-dim)', fontSize: 11.5 }}>{item.department}</span>
                      </>
                    ) : (
                      <span style={{ color: 'var(--text-dim)' }}>-</span>
                    )}
                  </td>
                  <td>
                    <span className={`badge ${statusBadgeClass(item.status)}`}>{item.status}</span>
                  </td>
                  <td>
                    <button
                      className="btn btn-ghost"
                      type="button"
                      disabled={loading}
                      onClick={() => onProcess(item.raw_text, item.id)}
                    >
                      {processingSubmissionId === item.id ? (
                        <>
                          <span className="spinner" />
                          AI 처리 중
                        </>
                      ) : (
                        'AI 처리 →'
                      )}
                    </button>
                  </td>
                </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
