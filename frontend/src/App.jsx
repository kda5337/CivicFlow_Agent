import Sidebar from './components/Sidebar.jsx'
import Topbar from './components/Topbar.jsx'
import Pipeline from './components/Pipeline.jsx'
import { ExternalLinkIcon } from './components/icons.jsx'
import DashboardView from './views/DashboardView.jsx'
import SubmissionsListView from './views/SubmissionsListView.jsx'
import AnsweredView from './views/AnsweredView.jsx'
import AnalysisView from './views/AnalysisView.jsx'
import RagView from './views/RagView.jsx'
import DraftView from './views/DraftView.jsx'
import ReviewView from './views/ReviewView.jsx'
import KnowledgeBaseView from './views/KnowledgeBaseView.jsx'
import PublicSubmitView from './views/PublicSubmitView.jsx'
import StaffView from './views/StaffView.jsx'
import { useInquiryPipeline } from './useInquiryPipeline.js'

// 사용자(시민)용 접수 페이지(/submit)와 부서 담당자용 업무 페이지(/staff)는 관리자용
// 내부 화면(Sidebar/Topbar/Pipeline)과 완전히 분리된 별도 경로다. 라우터 라이브러리
// 없이 경로만 보고 갈라진다 — 페이지가 몇 개 안 돼 굳이 의존성을 늘릴 필요가 없다.
const IS_PUBLIC_SUBMIT_ROUTE = window.location.pathname.startsWith('/submit')
const IS_STAFF_ROUTE = window.location.pathname.startsWith('/staff')

function App() {
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
    runInquiry,
    handleRegenerate,
    goToNext,
    goToPrev,
    handleDepartmentChange,
    handleProceedToReview,
    handleFinalizeAnswer,
    handleGenerateFromDocs,
  } = useInquiryPipeline('dashboard')

  if (IS_PUBLIC_SUBMIT_ROUTE) {
    return <PublicSubmitView />
  }

  if (IS_STAFF_ROUTE) {
    return <StaffView />
  }

  return (
    <div className="app">
      <Sidebar
        activeView={activeView}
        onNavigate={setActiveView}
        footer={
          <>
            <a className="sidebar-public-link" href="/submit" target="_blank" rel="noreferrer">
              <ExternalLinkIcon />
              <span>사용자 접수 페이지 열기</span>
            </a>
            <a className="sidebar-public-link" href="/staff" target="_blank" rel="noreferrer">
              <ExternalLinkIcon />
              <span>담당자 업무 페이지 열기</span>
            </a>
          </>
        }
      />

      <div className="main">
        <Topbar activeView={activeView} />
        <Pipeline activeView={activeView} />

        <div className="content">
          {activeView === 'dashboard' && <DashboardView />}
          {activeView === 'submissions' && (
            <SubmissionsListView
              onProcess={runInquiry}
              loading={loading}
              processingSubmissionId={processingSubmissionId}
              processError={error}
            />
          )}
          {activeView === 'answered' && <AnsweredView />}
          {activeView === 'analysis' && (
            <AnalysisView
              result={result}
              onNext={goToNext}
              onDepartmentChange={handleDepartmentChange}
              originalDepartment={originalDepartment}
              departmentOverridden={departmentOverridden}
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
          {activeView === 'kb' && <KnowledgeBaseView />}
        </div>
      </div>
    </div>
  )
}

export default App
