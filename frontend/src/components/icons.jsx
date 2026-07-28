// 사이드바 네비게이션 아이콘. 원본 목업의 인라인 SVG를 그대로 옮겼다.
const common = { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: '1.8' }

export function DashboardIcon() {
  return (
    <svg {...common}>
      <rect x="3" y="3" width="7" height="9" rx="1.5" />
      <rect x="14" y="3" width="7" height="5" rx="1.5" />
      <rect x="14" y="12" width="7" height="9" rx="1.5" />
      <rect x="3" y="16" width="7" height="5" rx="1.5" />
    </svg>
  )
}

export function IntakeIcon() {
  return (
    <svg {...common}>
      <path d="M4 4h16v16H4z" />
      <path d="M4 9h16" />
      <path d="M8 4v5" />
    </svg>
  )
}

export function AnalysisIcon() {
  return (
    <svg {...common}>
      <circle cx="12" cy="12" r="3.2" />
      <path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1" />
    </svg>
  )
}

export function RagIcon() {
  return (
    <svg {...common}>
      <circle cx="10.5" cy="10.5" r="6.5" />
      <path d="M20 20l-4.5-4.5" />
    </svg>
  )
}

export function DraftIcon() {
  return (
    <svg {...common}>
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z" />
    </svg>
  )
}

export function KbIcon() {
  return (
    <svg {...common}>
      <path d="M4 19.5A2.5 2.5 0 016.5 17H20" />
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z" />
    </svg>
  )
}

export const ICONS_BY_VIEW = {
  dashboard: DashboardIcon,
  intake: IntakeIcon,
  analysis: AnalysisIcon,
  rag: RagIcon,
  draft: DraftIcon,
  kb: KbIcon,
}
