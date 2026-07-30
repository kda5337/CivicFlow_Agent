import { useEffect, useState } from 'react'
import Sidebar from '../components/Sidebar.jsx'
import Topbar from '../components/Topbar.jsx'
import Pipeline from '../components/Pipeline.jsx'
import AnswerCacheDialog from '../components/AnswerCacheDialog.jsx'
import DashboardView from './DashboardView.jsx'
import SubmissionsListView from './SubmissionsListView.jsx'
import AnsweredView from './AnsweredView.jsx'
import AnalysisView from './AnalysisView.jsx'
import RagView from './RagView.jsx'
import DraftView from './DraftView.jsx'
import ReviewView from './ReviewView.jsx'
import { VIEWS } from '../viewsConfig.js'
import { useInquiryPipeline } from '../useInquiryPipeline.js'

const DEPARTMENTS_URL = 'http://localhost:8000/departments'
const STAFF_DEPARTMENT_KEY = 'civicflow_staff_department'

// 담당자용 업무 페이지(/staff). 관리자용 화면(App.jsx)과 똑같은 문의 처리 파이프라인을
// 공유하지만(useInquiryPipeline), 로그인이 없는 구조라 "이 브라우저를 쓰는 담당자가
// 어느 부서 소속인지"를 부서 선택 화면으로 한 번 물어본 뒤, 문의 접수함/답변 완료함/
// 대시보드를 전부 그 부서로만 걸러서 보여준다(SubmissionsListView/AnsweredView/
// DashboardView의 lockDepartment). 지식베이스 관리(원본 데이터를 바꾸는 화면)와
// Langfuse 트레이스 링크(내부 디버깅용)는 관리자 전용이라 이 페이지에는 없다 —
// 각각 STAFF_VIEWS에서 kb를 빼고, DraftView에 hideTraceLink를 넘겨서 뺀다.
// 담당부서 재배정(AnalysisView)은 관리자용과 동일하게 그대로 둔다 — AI가 잘못
// 분류한 문의를 다른 부서로 넘기는 것도 그 부서 업무 처리의 일부이기 때문이다.
const STAFF_VIEWS = VIEWS.filter((view) => view.key !== 'kb' && view.key !== 'test')

function DepartmentGate({ onConfirm }) {
  const [departments, setDepartments] = useState([])
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch(DEPARTMENTS_URL)
      .then((response) => {
        if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
        return response.json()
      })
      .then(setDepartments)
      .catch((err) => setError(err.message))
  }, [])

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--bg)',
        padding: 20,
      }}
    >
      <div className="card" style={{ width: 440, maxWidth: '100%' }}>
        <h2 className="section-title">소속 부서를 선택해 주세요</h2>
        <p style={{ fontSize: 12.5, color: 'var(--text-dim)', marginTop: -6, marginBottom: 18 }}>
          선택한 부서와 관련된 문의만 모아서 보여드립니다.
        </p>
        {error && <div className="error-banner">부서 목록을 불러오지 못했습니다: {error}</div>}
        <div className="dept-picker">
          {departments.map((dept) => (
            <button key={dept} type="button" className="dept-chip" onClick={() => onConfirm(dept)}>
              {dept}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

export default function StaffView() {
  const [department, setDepartment] = useState(() => localStorage.getItem(STAFF_DEPARTMENT_KEY) || '')

  // 관리자용 화면은 대시보드부터 보여주지만, 담당자는 곧바로 처리할 문의 목록부터
  // 보는 게 자연스러워 문의 접수함을 기본 화면으로 둔다.
  const {
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
    pendingCacheDecision,
    isBlankDraft,
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
  } = useInquiryPipeline('submissions')

  const handleConfirmDepartment = (dept) => {
    localStorage.setItem(STAFF_DEPARTMENT_KEY, dept)
    setDepartment(dept)
  }

  const handleSwitchDepartment = () => {
    localStorage.removeItem(STAFF_DEPARTMENT_KEY)
    setDepartment('')
    setActiveView('submissions')
  }

  // "AI 분석 결과"에서 담당자가 담당부서를 다른 부서로 바꾸고 "네, 담당 부서를
  // 변경합니다"를 눌렀을 때 호출된다. 실제 저장은 dept-chip을 누른 시점에 이미
  // handleDepartmentChange가 처리해뒀으니, 여기서는 문의 접수함으로 돌아가기만
  // 하면 된다 — 문의 접수함은 lockDepartment로 이 부서만 걸러 보여주므로, 방금
  // 다른 부서로 넘긴 문의는 다시 그 목록에 뜨지 않는다.
  const handleConfirmDepartmentChange = () => {
    setActiveView('submissions')
  }

  if (!department) {
    return <DepartmentGate onConfirm={handleConfirmDepartment} />
  }

  return (
    <div className="app">
      <AnswerCacheDialog
        pending={pendingCacheDecision}
        onResolve={resolveCacheDecision}
        onClose={dismissCacheDecision}
      />
      <Sidebar
        activeView={activeView}
        onNavigate={setActiveView}
        views={STAFF_VIEWS}
        footer={
          <button type="button" className="sidebar-public-link" onClick={handleSwitchDepartment}>
            <span>{department} · 부서 변경</span>
          </button>
        }
      />

      <div className="main">
        <Topbar activeView={activeView} userLabel={`담당자 · ${department}`} />
        <Pipeline activeView={activeView} />

        <div className="content">
          {activeView === 'dashboard' && <DashboardView lockDepartment={department} />}
          {activeView === 'submissions' && (
            <SubmissionsListView
              onProcess={handleProcessClick}
              loading={loading}
              processingSubmissionId={processingSubmissionId}
              processError={error}
              lockDepartment={department}
            />
          )}
          {activeView === 'answered' && <AnsweredView lockDepartment={department} />}
          {activeView === 'analysis' && (
            <AnalysisView
              result={result}
              onNext={goToNext}
              onBackToSubmissions={() => setActiveView('submissions')}
              onDepartmentChange={handleDepartmentChange}
              originalDepartment={originalDepartment}
              departmentOverridden={departmentOverridden}
              onConfirmDepartmentChange={handleConfirmDepartmentChange}
            />
          )}
          {activeView === 'rag' && (
            <RagView
              result={result}
              onNext={goToNext}
              onPrev={goToPrev}
              onGenerateFromDocs={handleGenerateFromDocs}
              generating={docRegenerating}
              generateError={docRegenerateError}
              currentSourceDocs={answerSourceDocs}
              onStartBlankDraft={handleStartBlankDraft}
            />
          )}
          {activeView === 'draft' && (
            <DraftView
              result={result}
              onRegenerate={handleRegenerate}
              loading={loading}
              onPrev={goToPrev}
              answerSourceDocs={answerSourceDocs}
              sources={answerSources}
              onProceedToReview={handleProceedToReview}
              hideTraceLink
              isBlankDraft={isBlankDraft}
            />
          )}
          {activeView === 'review' && (
            <ReviewView
              result={result}
              reviewText={reviewText}
              sources={answerSources}
              onPrev={goToPrev}
              onFinalize={handleFinalizeAnswer}
              isLinkedToSubmission={Boolean(linkedSubmissionId)}
            />
          )}
        </div>
      </div>
    </div>
  )
}
