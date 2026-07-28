import { useState } from 'react'
import Sidebar from './components/Sidebar.jsx'
import Topbar from './components/Topbar.jsx'
import Pipeline from './components/Pipeline.jsx'
import DashboardView from './views/DashboardView.jsx'
import IntakeView from './views/IntakeView.jsx'
import AnalysisView from './views/AnalysisView.jsx'
import RagView from './views/RagView.jsx'
import DraftView from './views/DraftView.jsx'
import KnowledgeBaseView from './views/KnowledgeBaseView.jsx'
import { nextPipelineView, previousPipelineView } from './viewsConfig.js'

const API_URL = 'http://localhost:8000/inquiries'
const REGENERATE_URL = 'http://localhost:8000/inquiries/regenerate-answer'

function App() {
  const [activeView, setActiveView] = useState('dashboard')
  const [submittedText, setSubmittedText] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [originalDepartment, setOriginalDepartment] = useState(null)
  const [departmentOverridden, setDepartmentOverridden] = useState(false)
  const [answerSourceDocs, setAnswerSourceDocs] = useState([])
  const [answerSources, setAnswerSources] = useState([])
  const [docRegenerating, setDocRegenerating] = useState(false)
  const [docRegenerateError, setDocRegenerateError] = useState(null)

  const runInquiry = async (text) => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      })
      if (!response.ok) {
        throw new Error(`${response.status} ${response.statusText}`)
      }
      const json = await response.json()
      setSubmittedText(text)
      setResult(json)
      setOriginalDepartment(json.classification?.담당부서 ?? null)
      setDepartmentOverridden(false)
      // 자동 생성된 답변은 검색된 문서 중 유사도 1위 하나만 근거로 쓴다(백엔드
      // generate_node와 동일한 기본값) — 담당자가 RAG 화면에서 문서를 직접 골라
      // 다시 생성하기 전까지는 이 값으로 표시한다.
      setAnswerSourceDocs((json.retrieved_docs || []).slice(0, 1))
      setAnswerSources(json.sources || [])
      setDocRegenerateError(null)
      setActiveView('analysis')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleRegenerate = () => {
    if (submittedText) runInquiry(submittedText)
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
  // App에서 들고 있어서, 다른 단계(RAG/답변 초안)로 갔다가 분석 결과로 돌아와도
  // 고친 부서가 그대로 유지된다.
  const handleDepartmentChange = (department) => {
    setResult((prev) =>
      prev ? { ...prev, classification: { ...prev.classification, 담당부서: department } } : prev
    )
    setDepartmentOverridden(department !== originalDepartment)
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

  return (
    <div className="app">
      <Sidebar activeView={activeView} onNavigate={setActiveView} />

      <div className="main">
        <Topbar activeView={activeView} />
        <Pipeline activeView={activeView} />

        <div className="content">
          {activeView === 'dashboard' && <DashboardView />}
          {activeView === 'intake' && (
            <IntakeView onSubmit={runInquiry} loading={loading} error={error} />
          )}
          {activeView === 'analysis' && (
            <AnalysisView
              result={result}
              onNext={goToNext}
              onPrev={goToPrev}
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
            />
          )}
          {activeView === 'kb' && <KnowledgeBaseView />}
        </div>
      </div>
    </div>
  )
}

export default App
