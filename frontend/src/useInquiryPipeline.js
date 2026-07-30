import { useState } from 'react'
import { nextPipelineView, previousPipelineView } from './viewsConfig.js'

const API_URL = 'http://localhost:8000/inquiries'
const REGENERATE_URL = 'http://localhost:8000/inquiries/regenerate-answer'
const SUBMISSIONS_URL = 'http://localhost:8000/submissions'

// 관리자용 화면(App.jsx)과 담당자용 화면(StaffView.jsx)이 똑같은 문의 처리 파이프라인
// (문의 접수함 → "AI 처리" → 분석 → RAG → 초안 → 검토)을 쓰기 때문에 그 상태와 로직을
// 여기 하나로 모아 둘 다 재사용한다. 두 화면은 각자 이 훅을 따로 호출하므로 상태는
// 서로 완전히 독립적이다(같은 브라우저에서 두 탭을 동시에 열어도 서로 영향을 주지 않는다).
export function useInquiryPipeline(initialView = 'dashboard') {
  const [activeView, setActiveView] = useState(initialView)
  const [submittedText, setSubmittedText] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  // runInquiry를 부른 문의 접수함 항목의 id. "AI 처리 →" 버튼이 처리 중에는 다시
  // 눌리지 않도록, 문의 접수함이 이 값을 보고 어느 버튼을 잠글지 판단한다.
  const [processingSubmissionId, setProcessingSubmissionId] = useState(null)
  const [error, setError] = useState(null)
  const [originalDepartment, setOriginalDepartment] = useState(null)
  const [departmentOverridden, setDepartmentOverridden] = useState(false)
  const [answerSourceDocs, setAnswerSourceDocs] = useState([])
  const [answerSources, setAnswerSources] = useState([])
  const [docRegenerating, setDocRegenerating] = useState(false)
  const [docRegenerateError, setDocRegenerateError] = useState(null)
  // 문의 접수함에서 "AI 처리 →"로 넘어온 경우에만 채워진다. 채워져 있으면 분류
  // 결과/최종 답변을 원본 citizen_submissions 레코드에도 그대로 반영한다 — 담당자가
  // '문의 접수'에서 직접 새로 입력한 문의는 citizen_submissions와 무관하므로 null.
  const [linkedSubmissionId, setLinkedSubmissionId] = useState(null)
  // 답변 초안 화면에서 담당자가 편집을 마친 텍스트. "검토하기"를 누르는 순간의
  // 스냅샷이라, 검토 화면에서 뒤로 갔다 다시 돌아와도 그 시점 내용이 유지된다.
  const [reviewText, setReviewText] = useState('')
  // 지금 result가 테스트 섹션에서 실행된 것인지. "AI 재생성 요청"(handleRegenerate)이
  // 이 값을 그대로 재사용해야, 테스트 문의를 재생성할 때도 캐시 조회/저장을 계속
  // 건너뛴다 — 안 그러면 재생성 시점에 진짜 캐시를 오염시키게 된다.
  const [isTestRun, setIsTestRun] = useState(false)
  // "AI 처리 →"를 눌렀을 때 answer_cache 히트가 있으면 여기 { text, submissionId,
  // finalAnswer, sources }가 채워진다. null이 아니면 화면에 "캐시 답변을 쓸지" 확인
  // 팝업을 띄운다 — 담당자가 선택하면 그 결과를 들고 runInquiry를 이어서 부른다.
  const [pendingCacheDecision, setPendingCacheDecision] = useState(null)
  // RAG 검색 결과 화면에서 근거가 부족하다고 판단해 "빈 화면에서 직접 작성"을 눌렀는지.
  // true면 답변 초안 화면의 draft_answer가 AI 생성이 아니라 담당자가 처음부터 쓴 것임을
  // 수정 이력에 다르게 표시한다. 새로 문의를 처리하거나(runInquiry) 문서로 재생성하면
  // (handleGenerateFromDocs) 다시 AI 생성 기반으로 돌아오므로 false로 초기화한다.
  const [isBlankDraft, setIsBlankDraft] = useState(false)

  const syncClassificationToSubmission = async (submissionId, classification, ruleFlags) => {
    try {
      await fetch(`${SUBMISSIONS_URL}/${submissionId}/classification`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          inquiry_type: classification.문의유형,
          inquiry_types: classification.문의유형들 || [],
          department: classification.담당부서,
          candidate_departments: ruleFlags?.candidate_departments || [],
          priority: classification.우선순위,
          emotion: classification.감정상태,
          core_request: classification.핵심요청,
          classification_reason: classification.분류근거,
          requires_manager_review: Boolean(ruleFlags?.requires_manager_review),
        }),
      })
    } catch {
      // 원본 접수 건 동기화는 부가 기능이라, 실패해도 담당자의 현재 작업(분석 결과
      // 화면)을 막지 않는다.
    }
  }

  // isTest: 관리자용 "테스트" 섹션에서 호출하면 true. submissionId 없이 항상 새로
  // 실행되며(citizen_submissions에 원래도 안 남음), 백엔드가 이 값을 보고 의미 캐시
  // 조회/저장도 건너뛴다(query_cache 오염 방지).
  // useAnswerCache: handleProcessClick이 캐시 히트를 미리 확인해 담당자에게 물어본 뒤
  // 그 선택(true/false)을 넘길 때 쓴다. undefined면 백엔드가 알아서 조회해 있으면 쓴다.
  const runInquiry = async (text, submissionId = null, { isTest = false, useAnswerCache } = {}) => {
    setLoading(true)
    setProcessingSubmissionId(submissionId)
    setError(null)
    try {
      const response = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        // 문의 접수함에서 "AI 처리"로 넘어온 경우(submissionId 있음)는 사용자용 접수
        // 페이지를 거치며 intake(관련성 판별)와 classify_node+rules_node(문의유형/
        // 담당부서/우선순위/감정상태 분류)가 이미 한 번 검증을 마친 문의다. 백엔드가
        // submission_id를 받으면 이 둘을 다시 돌리지 않고 그 결과를 그대로 가져와
        // RAG 검색+답변 생성만 수행한다.
        body: JSON.stringify({
          text,
          submission_id: submissionId,
          skip_relevance_check: Boolean(submissionId),
          is_test: isTest,
          use_answer_cache: useAnswerCache,
        }),
      })
      if (!response.ok) {
        throw new Error(`${response.status} ${response.statusText}`)
      }
      const json = await response.json()
      setSubmittedText(text)
      setResult(json)
      setLinkedSubmissionId(submissionId)
      setIsTestRun(isTest)
      setOriginalDepartment(json.classification?.담당부서 ?? null)
      setDepartmentOverridden(false)
      // 캐시 히트로 채워진 답변은 캐시에 있던 출처 전부가 그 답변의 근거였으므로 전부
      // "현재 답변 근거"로 표시하고, 새로 생성된 답변은 기존과 동일하게 유사도 1위 문서
      // 하나만 근거로 쓴다(백엔드 generate_node와 동일한 기본값).
      setAnswerSourceDocs(json.cache_hit ? json.retrieved_docs || [] : (json.retrieved_docs || []).slice(0, 1))
      setAnswerSources(json.sources || [])
      setDocRegenerateError(null)
      setReviewText('')
      setIsBlankDraft(false)
      setActiveView('analysis')

      if (submissionId && json.classification) {
        syncClassificationToSubmission(submissionId, json.classification, json.rule_flags)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
      setProcessingSubmissionId(null)
    }
  }

  const handleRegenerate = () => {
    if (submittedText) runInquiry(submittedText, linkedSubmissionId, { isTest: isTestRun })
  }

  // 문의 접수함의 "AI 처리 →" 버튼이 실제로 부르는 함수. submissionId가 있는 건(=실제
  // 시민 접수 건)만 answer_cache를 먼저 확인한다 — 테스트 섹션처럼 submissionId 없이
  // 직접 부르는 경우는 캐시 확인 대상이 아니라 바로 runInquiry로 진행한다. 캐시가
  // 있으면 화면에 확인 팝업을 띄우기 위해 pendingCacheDecision을 채우고, 담당자의
  // 선택은 resolveCacheDecision이 이어받는다.
  const handleProcessClick = async (text, submissionId = null, options) => {
    if (!submissionId) {
      runInquiry(text, submissionId, options)
      return
    }
    try {
      const response = await fetch(`${API_URL}/answer-cache-check`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ submission_id: submissionId }),
      })
      if (response.ok) {
        const check = await response.json()
        if (check.cache_hit) {
          setPendingCacheDecision({
            text,
            submissionId,
            finalAnswer: check.final_answer,
            sources: check.sources,
          })
          return
        }
      }
      // 확인 요청 자체가 실패해도(네트워크 오류 등) 처리를 막지는 않는다 — 캐시 확인
      // 없이 기존처럼 새로 생성하는 쪽으로 진행한다.
    } catch {
      // 위와 동일한 이유로 무시하고 진행한다.
    }
    runInquiry(text, submissionId, options)
  }

  // 캐시 확인 팝업에서 담당자가 버튼을 눌렀을 때 호출된다. useCache=true면 그 캐시
  // 답변을 그대로 쓰고, false면 "새로 생성"으로 기존 파이프라인을 그대로 돈다.
  const resolveCacheDecision = (useCache) => {
    const decision = pendingCacheDecision
    setPendingCacheDecision(null)
    if (!decision) return
    runInquiry(decision.text, decision.submissionId, { useAnswerCache: useCache })
  }

  // 팝업의 x(닫기)를 눌렀을 때 호출된다. 캐시 사용/새로 생성 중 아무것도 선택하지 않고
  // "AI 처리" 시도 자체를 취소한다 — runInquiry를 부르지 않으므로 문의 접수함에 그대로
  // 남아있고, processingSubmissionId도 채워진 적이 없어 버튼 잠금도 없다.
  const dismissCacheDecision = () => {
    setPendingCacheDecision(null)
  }

  const goToNext = () => {
    const next = nextPipelineView(activeView)
    if (next) setActiveView(next)
  }

  const goToPrev = () => {
    const prev = previousPipelineView(activeView)
    if (prev) setActiveView(prev)
  }

  // 담당자가 AI가 고른 담당부서가 틀렸다고 판단해 직접 고쳤을 때 쓴다. result를
  // 여기서 들고 있어서, 다른 단계(RAG/답변 초안)로 갔다가 분석 결과로 돌아와도
  // 고친 부서가 그대로 유지된다.
  const handleDepartmentChange = (department) => {
    setResult((prev) => {
      if (!prev) return prev
      const nextResult = { ...prev, classification: { ...prev.classification, 담당부서: department } }
      if (linkedSubmissionId) {
        syncClassificationToSubmission(linkedSubmissionId, nextResult.classification, nextResult.rule_flags)
      }
      return nextResult
    })
    setDepartmentOverridden(department !== originalDepartment)
  }

  // 답변 초안 화면에서 "검토하기"를 누르면 그 시점 텍스트를 들고 검토 단계로 넘어간다.
  // 실제 저장(등록)은 검토 화면의 "검토 완료 & 등록" 버튼이 한다.
  const handleProceedToReview = (text) => {
    setReviewText(text)
    goToNext()
  }

  // 검토 화면에서 "검토 완료 & 등록"을 눌렀을 때 호출된다. 이 문의가 사용자용 접수
  // 건에서 온 것이면(linkedSubmissionId) 그 원본 레코드에 확정 답변과 그 출처를 실제로
  // 저장한다 — 사용자 페이지의 '답변 확인' 탭이 바로 이 값을 보여주고, 백엔드는 이걸
  // answer_cache에도 등록해 비슷한 문의가 다시 오면 재사용한다. 실패하면 예외를 던져
  // 검토 화면이 "등록 실패"를 보여줄 수 있게 한다.
  const handleFinalizeAnswer = async (finalText) => {
    if (!linkedSubmissionId) return
    const response = await fetch(`${SUBMISSIONS_URL}/${linkedSubmissionId}/answer`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ final_answer: finalText, sources: answerSources }),
    })
    if (!response.ok) {
      throw new Error(`${response.status} ${response.statusText}`)
    }
  }

  // 담당자가 RAG 검색 결과 화면에서 문서를 직접 골라 그 문서(들)만 근거로 답변을
  // 다시 만든다. intake/classify/apply_rules/retrieve는 이미 끝난 뒤라 다시 돌 필요가
  // 없어서 generate 단계만 다시 부르는 전용 엔드포인트를 쓴다(전체 재실행보다 훨씬 빠름).
  const handleGenerateFromDocs = async (docs) => {
    if (!result || !docs.length) return
    setDocRegenerating(true)
    setDocRegenerateError(null)
    try {
      const response = await fetch(REGENERATE_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          raw_text: result.raw_text,
          classification: result.classification,
          docs,
        }),
      })
      if (!response.ok) {
        throw new Error(`${response.status} ${response.statusText}`)
      }
      const json = await response.json()
      setResult((prev) => (prev ? { ...prev, draft_answer: json.draft_answer } : prev))
      setAnswerSourceDocs(docs)
      setAnswerSources(json.sources || [])
      setIsBlankDraft(false)
      setActiveView('draft')
    } catch (err) {
      setDocRegenerateError(err.message)
    } finally {
      setDocRegenerating(false)
    }
  }

  // RAG 검색 결과 화면에서 근거 문서가 부족/없다고 판단했을 때 쓴다. AI가 만든(또는
  // 캐시로 채워진) 초안을 버리고, 담당자가 완전히 빈 화면에서 답변을 직접 쓰도록
  // 답변 초안 화면으로 바로 넘어간다.
  const handleStartBlankDraft = () => {
    setResult((prev) => (prev ? { ...prev, draft_answer: '' } : prev))
    setAnswerSourceDocs([])
    setAnswerSources([])
    setIsBlankDraft(true)
    setActiveView('draft')
  }

  return {
    activeView,
    setActiveView,
    result,
    loading,
    processingSubmissionId,
    error,
    originalDepartment,
    departmentOverridden,
    answerSourceDocs,
    answerSources,
    docRegenerating,
    docRegenerateError,
    linkedSubmissionId,
    reviewText,
    isTestRun,
    pendingCacheDecision,
    isBlankDraft,
    runInquiry,
    handleProcessClick,
    resolveCacheDecision,
    dismissCacheDecision,
    handleRegenerate,
    goToNext,
    goToPrev,
    handleDepartmentChange,
    handleProceedToReview,
    handleFinalizeAnswer,
    handleGenerateFromDocs,
    handleStartBlankDraft,
  }
}
