import { VIEW_TITLES } from '../viewsConfig.js'

export default function Topbar({ activeView, userLabel = '관리자 · 아무개' }) {
  return (
    <div className="topbar">
      <div className="topbar-title">{VIEW_TITLES[activeView]}</div>
      <div className="topbar-right">
        <div className="user-chip">
          <div className="user-dot" />
          {userLabel}
        </div>
      </div>
    </div>
  )
}
