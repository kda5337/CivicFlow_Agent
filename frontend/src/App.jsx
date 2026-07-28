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
import { nextPipelineView } from './viewsConfig.js'

const API_URL = 'http://localhost:8000/inquiries'

function App() {
  const [activeView, setActiveView] = useState('dashboard')
  const [submittedText, setSubmittedText] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

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
          {activeView === 'analysis' && <AnalysisView result={result} onNext={goToNext} />}
          {activeView === 'rag' && <RagView result={result} onNext={goToNext} />}
          {activeView === 'draft' && (
            <DraftView result={result} onRegenerate={handleRegenerate} loading={loading} />
          )}
          {activeView === 'kb' && <KnowledgeBaseView />}
        </div>
      </div>
    </div>
  )
}

export default App
