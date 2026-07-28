import { priorityBadgeClass } from '../priorityBadge.js'

// 실제 classify_node + rules_node 결과(state.classification, state.rule_flags)를
// 그대로 보여준다. 목업에 있던 "분류 신뢰도"(가짜 91% 수치)는 실제 API에 없는
// 값이라, 대신 실제로 존재하는 감정상태/핵심요청/분류근거로 대체했다.
export default function AnalysisView({ result, onNext }) {
  if (!result || !result.classification) {
    return (
      <div className="view" id="view-analysis">
        <div className="card empty-state">
          아직 분석된 문의가 없습니다.
          <br />
          '문의 접수' 화면에서 문의를 등록해 주세요.
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
            <span className="result-key">문의 유형</span>
            <span className="result-val">{classification.문의유형}</span>
          </div>
          <div className="result-row">
            <span className="result-key">담당 부서</span>
            <span className="result-val">{classification.담당부서}</span>
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
          <div style={{ fontSize: 12.5, color: 'var(--text-dim)', marginBottom: 6 }}>핵심 요청</div>
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
        <button className="btn btn-primary" type="button" onClick={onNext}>
          다음 단계: RAG 검색 결과 →
        </button>
      </div>
    </div>
  )
}
