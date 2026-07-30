import { PIPELINE_STEPS, VIEW_STEP_MAP } from '../viewsConfig.js'

export default function Pipeline({ activeView }) {
  const current = VIEW_STEP_MAP[activeView]
  if (current === -1) return null

  return (
    <div className="pipeline">
      {PIPELINE_STEPS.map((step, index) => {
        const cls = index < current ? 'done' : index === current ? 'now' : ''
        const dotContent = index < current ? '✓' : index + 1
        return (
          <div key={step} className={`p-step ${cls}`}>
            <div className="dot">{dotContent}</div>
            <div className="label">{step}</div>
            <div className="line" />
          </div>
        )
      })}
    </div>
  )
}
