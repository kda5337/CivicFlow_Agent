import { useEffect, useState } from 'react'
import { priorityBadgeClass } from '../priorityBadge.js'

const DEPARTMENTS_URL = 'http://localhost:8000/departments'

// 실제 classify_node + rules_node 결과(state.classification, state.rule_flags)를
// 그대로 보여준다. 목업에 있던 "분류 신뢰도"(가짜 91% 수치)는 실제 API에 없는
// 값이라, 대신 실제로 존재하는 감정상태/핵심요청/분류근거로 대체했다.
//
// 담당부서는 AI(rules_node)가 정한 값을 기본으로 보여주되, 담당자가 잘못됐다고
// 판단하면 rules.yaml에 있는 부서 전체를 버튼(칩)으로 골라 직접 고칠 수 있다.
// 고친 값은 App.jsx의 result 상태에 바로 반영되므로, 다른 단계로 갔다가 돌아와도
// 유지된다.
//
// onConfirmDepartmentChange가 있으면(담당자용 페이지) 부서를 바꾸는 순간부터 "다음
// 단계"를 막고, 정말 우리 부서 담당이 아닌 게 맞는지 한 번 더 확인시킨다 — 부서를
// 바꾼 문의는 그 담당자의 문의 접수함에서 사라지는(lockDepartment 필터에 걸리는)
// 되돌리기 번거로운 변화라, 실수로 칩을 잘못 눌러 문의를 놓치는 걸 막기 위해서다.
// 관리자용 화면은 이 prop을 넘기지 않아 기존처럼 바로 다음 단계로 넘어갈 수 있다.
export default function AnalysisView({
  result,
  onNext,
  onDepartmentChange,
  originalDepartment,
  departmentOverridden,
  onConfirmDepartmentChange,
}) {
  const [departments, setDepartments] = useState([])

  useEffect(() => {
    fetch(DEPARTMENTS_URL)
      .then((response) => response.json())
      .then(setDepartments)
      .catch(() => setDepartments([]))
  }, [])

  if (!result) {
    return (
      <div className="view" id="view-analysis">
        <div className="card empty-state">
          아직 분석된 문의가 없습니다.
          <br />
          '문의 접수함'에서 문의를 선택해 "AI 처리 →"를 눌러 주세요.
        </div>
      </div>
    )
  }

  if (!result.classification) {
    // relevance_check.관련여부가 false면 intake에서 재질문 요청으로 끝나 분류 자체가
    // 없다 — "아직 처리 안 함"이 아니라 "처리했지만 대상 아님으로 판단함"이므로 구분해서 보여준다.
    const reason = result.relevance_check?.판단근거
    return (
      <div className="view" id="view-analysis">
        <div className="card empty-state">
          AI가 이 문의를 처리 대상(민원·문의)이 아니라고 판단해 분류하지 않았습니다.
          {reason && (
            <>
              <br />
              판단 근거: {reason}
            </>
          )}
          <br />
          실제로 처리가 필요한 문의라면 담당자가 직접 분류/답변해 주세요.
        </div>
      </div>
    )
  }

  const classification = result.classification
  const ruleFlags = result.rule_flags || {}
  const candidateDepartments = ruleFlags.candidate_departments || []
  const matchedRules = ruleFlags.matched_rules || []

  return (
    <div className="view" id="view-analysis">
      <div className="grid cols-2">
        <div className="card">
          <h2 className="section-title">분류 결과</h2>
          <div className="result-row">
            <span className="result-key">문의 유형(대표)</span>
            <span className="result-val">{classification.문의유형}</span>
          </div>
          <div className="result-row">
            <span className="result-key">문의 유형(전체)</span>
            <span className="result-val">
              {classification.문의유형들 && classification.문의유형들.length
                ? classification.문의유형들.join(', ')
                : classification.문의유형}
            </span>
          </div>
          <div className="result-row" style={{ alignItems: 'flex-start', flexDirection: 'column', gap: 8 }}>
            <span className="result-key">담당 부서 (틀렸다면 아래에서 직접 선택)</span>
            <div className="dept-picker">
              {(departments.length ? departments : [classification.담당부서]).map((dept) => (
                <button
                  key={dept}
                  type="button"
                  className={`dept-chip${dept === classification.담당부서 ? ' active' : ''}`}
                  onClick={() => onDepartmentChange(dept)}
                >
                  {dept}
                </button>
              ))}
            </div>
            {departmentOverridden && onConfirmDepartmentChange ? (
              <div
                style={{
                  background: 'var(--red-soft)',
                  border: '1px solid var(--red)',
                  borderRadius: 9,
                  padding: '10px 14px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 8,
                  width: '100%',
                }}
              >
                <div style={{ color: 'var(--red)', fontSize: 12.5, fontWeight: 600 }}>
                  ⚠ 이 문의가 우리 부서 담당이 아닌 것이 확실합니까? 부서를 변경하면 이 문의는 문의
                  접수함에서 사라집니다. (AI 원래 분류: {originalDepartment})
                </div>
                <button
                  className="btn btn-danger"
                  type="button"
                  style={{ alignSelf: 'flex-start' }}
                  onClick={() => onConfirmDepartmentChange(classification.담당부서)}
                >
                  네, 담당 부서를 변경합니다
                </button>
              </div>
            ) : (
              departmentOverridden && (
                <div className="dept-override-note">
                  담당자가 수동으로 수정함 (AI 원래 분류: {originalDepartment})
                </div>
              )
            )}
          </div>
          <div className="result-row">
            <span className="result-key">담당부서 후보</span>
            <span className="result-val">
              {candidateDepartments.length ? candidateDepartments.join(', ') : '(없음)'}
            </span>
          </div>
          <div className="result-row">
            <span className="result-key">우선순위</span>
            <span className={`badge ${priorityBadgeClass(classification.우선순위)}`}>
              {classification.우선순위}
            </span>
          </div>
          <div className="result-row">
            <span className="result-key">감정 상태</span>
            <span className="result-val">{classification.감정상태}</span>
          </div>
          {ruleFlags.requires_manager_review && (
            <div className="result-row">
              <span className="result-key">관리자 검토</span>
              <span className="badge high">즉시 검토 필요</span>
            </div>
          )}
        </div>

        <div className="card">
          <h2 className="section-title">분류 근거</h2>
          <div style={{ fontSize: 12.5, color: 'var(--text-dim)', marginBottom: 6 }}>사용자 입력</div>
          <div style={{ fontSize: 13.5, whiteSpace: 'pre-wrap' }}>{result.raw_text}</div>

          <div style={{ fontSize: 12.5, color: 'var(--text-dim)', margin: '14px 0 6px' }}>핵심 요청</div>
          <div style={{ fontSize: 13.5 }}>{classification.핵심요청}</div>

          <div style={{ fontSize: 12.5, color: 'var(--text-dim)', margin: '14px 0 4px' }}>LLM 분류 근거</div>
          <div style={{ fontSize: 13.5 }}>{classification.분류근거}</div>

          <div style={{ fontSize: 12.5, color: 'var(--text-dim)', margin: '14px 0 4px' }}>규칙 엔진 매칭 경로</div>
          <div className="rule-trace">
            {matchedRules.length
              ? matchedRules.map((rule, index) => (
                  <span key={rule}>
                    {rule}
                    {index < matchedRules.length - 1 && <span className="arrow">→</span>}
                  </span>
                ))
              : '(매칭된 규칙 없음)'}
          </div>
        </div>
      </div>

      <div className="form-actions">
        <button
          className="btn btn-primary"
          type="button"
          onClick={onNext}
          disabled={Boolean(departmentOverridden && onConfirmDepartmentChange)}
        >
          다음 단계: RAG 검색 결과 →
        </button>
      </div>
    </div>
  )
}
