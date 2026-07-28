import { VIEW_TITLES } from '../viewsConfig.js'

export default function Topbar({ activeView }) {
  return (
    <div className="topbar">
      <div className="topbar-title">{VIEW_TITLES[activeView]}</div>
      <div className="topbar-right">
        <div className="user-chip">
          <div className="user-dot" />
          담당자 · 김민지
        </div>
      </div>
    </div>
  )
}
