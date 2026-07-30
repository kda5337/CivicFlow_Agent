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

// views: 메뉴로 보여줄 화면 목록(기본은 관리자용 VIEWS 전체). 담당자용 페이지
// (StaffView)는 지식베이스 관리를 뺀 목록을 넘겨서 메뉴에서 아예 안 보이게 한다.
// footer: 하단에 고정으로 보여줄 내용(관리자는 외부 페이지 링크들, 담당자는 부서
// 변경 버튼) — 화면마다 다르니 호출하는 쪽에서 그대로 넘겨받는다.
export default function Sidebar({ activeView, onNavigate, views = VIEWS, footer }) {
  const groups = groupBy(views)

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

      {footer && <div className="sidebar-links">{footer}</div>}

      <div className="sidebar-foot">
        LangGraph StateGraph 기반
        <br />
        자동 분류 · RAG · 규칙엔진
      </div>
    </div>
  )
}
