import { Fragment, useEffect, useState } from 'react'
import { priorityBadgeClass } from '../priorityBadge.js'
import DepartmentFilter, { ALL_DEPARTMENTS } from '../components/DepartmentFilter.jsx'
import { API_BASE_URL } from '../config.js'

const SUBMISSIONS_URL = `${API_BASE_URL}/submissions`

// 담당자가 이미 답변까지 확정한 문의(citizen_submissions.status === '답변완료')만
// 모아 보여주는 모니터링 화면. GET /submissions는 필터링 기능이 없어 전체를 받아온
// 뒤 프론트에서 상태로 걸러낸다 — 문의 접수함(SubmissionsListView)과 같은 데이터를
// 다른 관점(사용자 입력 + 분류 결과 + 확정 답변을 한 번에)으로 보여주는 용도라
// 별도 엔드포인트를 새로 만들 필요는 없다.
// lockDepartment: 담당자용 페이지(StaffView)에서 넘겨주면, 그 부서로 고정하고 부서
// 선택 칩 자체를 숨긴다 — SubmissionsListView와 같은 패턴.
export default function AnsweredView({ lockDepartment }) {
  const [submissions, setSubmissions] = useState(null)
  const [error, setError] = useState(null)
  const [openId, setOpenId] = useState(null)
  const [deptFilter, setDeptFilter] = useState(ALL_DEPARTMENTS)
  const effectiveDeptFilter = lockDepartment || deptFilter

  const load = () => {
    setError(null)
    fetch(SUBMISSIONS_URL)
      .then((response) => {
        if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
        return response.json()
      })
      .then((data) => setSubmissions(data.filter((item) => item.status === '답변완료')))
      .catch((err) => setError(err.message))
  }

  useEffect(() => {
    load()
  }, [])

  const visibleSubmissions = submissions
    ? submissions.filter((item) => effectiveDeptFilter === ALL_DEPARTMENTS || item.department === effectiveDeptFilter)
    : null

  return (
    <div className="view" id="view-answered">
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <h2 className="section-title" style={{ margin: 0 }}>
            답변 완료함 {visibleSubmissions ? `(${visibleSubmissions.length}건)` : ''}
          </h2>
          <button className="btn btn-ghost" type="button" onClick={load}>
            새로고침
          </button>
        </div>

        {!lockDepartment && <DepartmentFilter value={deptFilter} onChange={setDeptFilter} />}

        {error && <div className="error-banner">목록을 불러오지 못했습니다: {error}</div>}

        {visibleSubmissions && visibleSubmissions.length === 0 && (
          <div className="empty-state">
            {effectiveDeptFilter === ALL_DEPARTMENTS
              ? '아직 답변을 확정한 문의가 없습니다.'
              : `'${effectiveDeptFilter}' 담당의 답변 완료 문의가 없습니다.`}
          </div>
        )}

        {visibleSubmissions && visibleSubmissions.length > 0 && (
          <table>
            <tbody>
              <tr>
                <th></th>
                <th>접수 시각</th>
                <th>이름</th>
                <th>사용자 입력</th>
                <th>분류 결과</th>
                <th>우선순위</th>
                <th></th>
              </tr>
              {visibleSubmissions.map((item) => {
                const isOpen = openId === item.id
                return (
                  <Fragment key={item.id}>
                    <tr
                      style={
                        item.requires_manager_review
                          ? { background: 'var(--red-soft)', boxShadow: 'inset 3px 0 0 var(--red)' }
                          : undefined
                      }
                    >
                      <td>
                        {item.requires_manager_review && (
                          <span className="badge high" title="rules.yaml 민감 민원 규칙에 걸려 즉시 검토가 필요했던 건입니다">
                            ⚠
                          </span>
                        )}
                      </td>
                      <td className="mono" style={{ whiteSpace: 'nowrap' }}>
                        {new Date(item.submitted_at).toLocaleString('ko-KR')}
                      </td>
                      <td>{item.name}</td>
                      <td style={{ maxWidth: 320 }}>{item.raw_text}</td>
                      <td style={{ whiteSpace: 'nowrap' }}>
                        {item.inquiry_type}
                        <br />
                        <span style={{ color: 'var(--text-dim)', fontSize: 11.5 }}>{item.department}</span>
                      </td>
                      <td>
                        <span className={`badge ${priorityBadgeClass(item.priority)}`}>{item.priority}</span>
                      </td>
                      <td>
                        <button
                          className="btn btn-ghost"
                          type="button"
                          onClick={() => setOpenId(isOpen ? null : item.id)}
                        >
                          {isOpen ? '접기' : '자세히 보기'}
                        </button>
                      </td>
                    </tr>
                    {isOpen && (
                      <tr key={`${item.id}-detail`}>
                        <td></td>
                        <td colSpan={6} style={{ padding: '4px 0 18px' }}>
                          <div className="grid cols-2">
                            <div className="card" style={{ background: 'var(--bg)' }}>
                              <h3 className="section-title" style={{ fontSize: 13 }}>
                                사용자 입력 · 분류 결과
                              </h3>
                              <div className="result-row">
                                <span className="result-key">연락처</span>
                                <span className="result-val">{item.contact}</span>
                              </div>
                              <div className="result-row">
                                <span className="result-key">문의 유형(전체)</span>
                                <span className="result-val">
                                  {item.inquiry_types.length ? item.inquiry_types.join(', ') : item.inquiry_type}
                                </span>
                              </div>
                              <div className="result-row">
                                <span className="result-key">담당부서 후보</span>
                                <span className="result-val">
                                  {item.candidate_departments.length ? item.candidate_departments.join(', ') : '(없음)'}
                                </span>
                              </div>
                              <div className="result-row">
                                <span className="result-key">감정 상태</span>
                                <span className="result-val">{item.emotion || '-'}</span>
                              </div>
                              <div className="result-row" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 6 }}>
                                <span className="result-key">핵심 요청</span>
                                <span className="result-val">{item.core_request || '-'}</span>
                              </div>
                              <div className="result-row" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 6 }}>
                                <span className="result-key">분류 근거</span>
                                <span className="result-val">{item.classification_reason || '-'}</span>
                              </div>
                            </div>
                            <div className="card" style={{ background: 'var(--bg)' }}>
                              <h3 className="section-title" style={{ fontSize: 13 }}>
                                확정 답변
                              </h3>
                              <div style={{ fontSize: 13.5, lineHeight: 1.75, whiteSpace: 'pre-wrap' }}>
                                {item.final_answer}
                              </div>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
