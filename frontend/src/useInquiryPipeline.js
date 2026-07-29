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

  const runInquiry = async (text, submissionId = null) => {
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
        body: JSON.stringify({ text, submission_id: submissionId, skip_relevance_check: Boolean(submissionId) }),
      })
      if (!response.ok) {
        throw new Error(`${response.status} ${response.statusText}`)
      }
      const json = await response.json()
      setSubmittedText(text)
      setResult(json)
      setLinkedSubmissionId(submissionId)
      setOriginalDepartment(json.classification?.담당부서 ?? null)
      setDepartmentOverridden(false)
      // 자동 생성된 답변은 검색된 문서 중 유사도 1위 하나만 근거로 쓴다(백엔드
      // generate_node와 동일한 기본값) — 담당자가 RAG 화면에서 문서를 직접 골라
      // 다시 생성하기 전까지는 이 값으로 표시한다.
      setAnswerSourceDocs((json.retrieved_docs || []).slice(0, 1))
      setAnswerSources(json.sources || [])
      setDocRegenerateError(null)
      setReviewText('')
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
    if (submittedText) runInquiry(submittedText, linkedSubmissionId)
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
  // 건에서 온 것이면(linkedSubmissionId) 그 원본 레코드에 확정 답변을 실제로
  // 저장한다 — 사용자 페이지의 '답변 확인' 탭이 바로 이 값을 보여준다. 실패하면
  // 예외를 던져 검토 화면이 "등록 실패"를 보여줄 수 있게 한다.
  const handleFinalizeAnswer = async (finalText) => {
    if (!linkedSubmissionId) return
    const response = await fetch(`${SUBMISSIONS_URL}/${linkedSubmissionId}/answer`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ final_answer: finalText }),
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
      setActiveView('draft')
    } catch (err) {
      setDocRegenerateError(err.message)
    } finally {
      setDocRegenerating(false)
    }
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
    runInquiry,
    handleRegenerate,
    goToNext,
    goToPrev,
    handleDepartmentChange,
    handleProceedToReview,
    handleFinalizeAnswer,
    handleGenerateFromDocs,
  }
}
