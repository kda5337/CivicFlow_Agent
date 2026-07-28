import { VIEWS } from '../viewsConfig.js'
import { ICONS_BY_VIEW } from './icons.jsx'

function groupBy(views) {
  const groups = []
  for (const view of views) {
    let group = groups.find((g) => g.name === view.group)
    if (!group) {
      group = { name: view.group, items: [] }
      groups.push(group)
    }
    group.items.push(view)
  }
  return groups
}

export default function Sidebar({ activeView, onNavigate }) {
  const groups = groupBy(VIEWS)

  return (
    <div className="sidebar">
      <div className="brand">
        <div className="brand-mark">CF</div>
        <div>
          <div className="brand-name">CivicFlow Agent</div>
          <div className="brand-sub">v0.9 · admin console</div>
        </div>
      </div>

      {groups.map((group) => (
        <div key={group.name}>
          <div className="nav-group-label">{group.name}</div>
          {group.items.map((view) => {
            const Icon = ICONS_BY_VIEW[view.key]
            return (
              <button
                key={view.key}
                type="button"
                className={`nav-item${activeView === view.key ? ' active' : ''}`}
                onClick={() => onNavigate(view.key)}
              >
                <Icon />
                <span>{view.label}</span>
                <span className="num">{view.num}</span>
              </button>
            )
          })}
        </div>
      ))}

      <div className="sidebar-foot">
        LangGraph StateGraph 기반
        <br />
        자동 분류 · RAG · 규칙엔진
      </div>
    </div>
  )
}
