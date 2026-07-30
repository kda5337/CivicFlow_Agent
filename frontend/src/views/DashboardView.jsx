import { useEffect, useState } from 'react'
import { priorityBadgeClass } from '../priorityBadge.js'
import { isDelayed } from '../delay.js'

const SUBMISSIONS_URL = 'http://localhost:8000/submissions'

// citizen_submissions.inquiry_type이 실제로 가질 수 있는 7개 값(classify_node 기준).
// 목업에 있던 "수강신청/장학금/시설민원/증명서/기타"는 이 시스템의 실제 분류 체계가
// 아니라서, 유형별 접수 현황 차트는 이 7개를 기준으로 다시 그린다.
const INQUIRY_TYPES = ['신청/등록', '변경/정정', '취소/환불', '오류/장애', '불만/신고', '안내/조회', '일반문의']

// 유형별로 막대 색을 다르게 해서 한눈에 구분되게 한다 — 앱 전반의 팔레트(teal/amber/red)
// 와 어울리게 확장한 색상표.
const TYPE_COLOR = {
  '신청/등록': '#0E8C86',
  '변경/정정': '#59B7B1',
  '취소/환불': '#D98C2B',
  '오류/장애': '#C6494A',
  '불만/신고': '#8B5FBF',
  '안내/조회': '#4C7EA6',
  일반문의: '#B9C0D4',
}

const PRIORITY_BUCKET_COLOR = { high: '#C6494A', mid: '#D98C2B', low: '#0E8C86' }
const PRIORITY_BUCKET_LABEL = { high: '高', mid: '中', low: '低' }
const CIRCLE_R = 45
const CIRCUMFERENCE = 2 * Math.PI * CIRCLE_R

function formatElapsed(submittedAt) {
  const hours = Math.floor((Date.now() - new Date(submittedAt).getTime()) / (60 * 60 * 1000))
  if (hours < 24) return `${hours}시간`
  const days = Math.floor(hours / 24)
  return `${days}일 ${hours % 24}시간`
}

// citizen_submissions은 답변완료 전환 시각을 저장하지 않아(submitted_at만 있음)
// "평균 처리 시간"은 이 데이터로 계산할 수 없다 — 그래서 이 화면에서 아예 제외했다.
// 나머지 통계는 모두 GET /submissions 하나로 실시간 계산한 실제 값이다.
// lockDepartment: 담당자용 페이지(StaffView)에서 넘겨주면, 모든 통계를 그 부서
// 것만으로 계산한다 — 관리자용 화면에서는 넘기지 않아 기존처럼 전체 통계를 보여준다.
export default function DashboardView({ lockDepartment }) {
  const [submissions, setSubmissions] = useState(null)
  const [error, setError] = useState(null)

  const load = () => {
    setError(null)
    fetch(SUBMISSIONS_URL)
      .then((response) => {
        if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
        return response.json()
      })
      .then((data) => setSubmissions(lockDepartment ? data.filter((s) => s.department === lockDepartment) : data))
      .catch((err) => setError(err.message))
  }

  useEffect(() => {
    load()
  }, [])

  if (error) {
    return (
      <div className="view" id="view-dashboard">
        <div className="error-banner">현황을 불러오지 못했습니다: {error}</div>
      </div>
    )
  }

  if (!submissions) {
    return (
      <div className="view" id="view-dashboard">
        <div className="card empty-state">불러오는 중...</div>
      </div>
    )
  }

  const answeredCount = submissions.filter((s) => s.status === '답변완료').length
  const openItems = submissions.filter((s) => s.status !== '답변완료')
  const delayedItems = openItems
    .filter((s) => isDelayed(s.submitted_at))
    .sort((a, b) => new Date(a.submitted_at) - new Date(b.submitted_at))
  const highPriorityOpenCount = openItems.filter((s) => priorityBadgeClass(s.priority) === 'high').length

  const typeCounts = INQUIRY_TYPES.map((type) => ({
    type,
    count: submissions.filter((s) => s.inquiry_type === type).length,
  }))
  const maxTypeCount = Math.max(1, ...typeCounts.map((t) => t.count))

  const priorityBuckets = ['high', 'mid', 'low'].map((bucket) => ({
    bucket,
    count: submissions.filter((s) => priorityBadgeClass(s.priority) === bucket).length,
  }))
  const total = submissions.length || 1
  let cumulative = 0
  const donutSegments = priorityBuckets.map(({ bucket, count }) => {
    const length = (count / total) * CIRCUMFERENCE
    const segment = { bucket, count, length, offset: -cumulative }
    cumulative += length
    return segment
  })

  return (
    <div className="view" id="view-dashboard">
      <h2 className="section-title">오늘의 처리 현황</h2>
      <div className="grid cols-4" style={{ marginBottom: 18 }}>
        <div className="card stat-card">
          <div className="stat-label">총 접수 건수</div>
          <div className="stat-value">{submissions.length}</div>
          <div className="stat-delta" style={{ color: 'var(--text-dim)' }}>
            누적 전체 문의 건수
          </div>
        </div>
        <div className="card stat-card">
          <div className="stat-label">처리 지연 건수</div>
          <div className="stat-value">{delayedItems.length}</div>
          <div className="stat-delta" style={{ color: 'var(--text-dim)' }}>
            접수 익일 오전 9시 초과 · 미답변
          </div>
        </div>
        <div className="card stat-card">
          <div className="stat-label">답변 완료 건수</div>
          <div className="stat-value" style={{ color: 'var(--teal)' }}>
            {answeredCount}
          </div>
          <div className="stat-delta" style={{ color: 'var(--text-dim)' }}>
            담당자가 최종 답변까지 확정한 건
          </div>
        </div>
        <div className="card stat-card">
          <div className="stat-label">우선순위 高</div>
          <div className="stat-value">{highPriorityOpenCount}</div>
          <div className="stat-delta" style={{ color: 'var(--text-dim)' }}>
            즉시 대응 필요 · 미답변
          </div>
        </div>
      </div>

      <div className="grid cols-2">
        <div className="card">
          <h2 className="section-title">유형별 접수 현황</h2>
          <svg viewBox="0 0 420 190" width="100%" height="190">
            <g fontFamily="JetBrains Mono" fontSize="10" fill="#66708A">
              {typeCounts.map(({ type, count }, i) => {
                const barWidth = 46
                const gap = 20
                const x = 20 + i * (barWidth + gap)
                const maxHeight = 120
                const height = maxTypeCount ? Math.max(4, (count / maxTypeCount) * maxHeight) : 4
                const y = 150 - height
                return (
                  <g key={type}>
                    <rect x={x} y={y} width={barWidth} height={height} rx="5" fill={TYPE_COLOR[type]} />
                    <text x={x + barWidth / 2} y="168" textAnchor="middle">
                      {type}
                    </text>
                    <text x={x + barWidth / 2} y={y - 6} textAnchor="middle" fill="#14213D" fontWeight="600">
                      {count}
                    </text>
                  </g>
                )
              })}
            </g>
          </svg>
        </div>

        <div className="card">
          <h2 className="section-title">우선순위 분포</h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
            <svg viewBox="0 0 120 120" width="130" height="130">
              <circle cx="60" cy="60" r={CIRCLE_R} fill="none" stroke="#EDEFF4" strokeWidth="16" />
              {donutSegments
                .filter((s) => s.count > 0)
                .map((s) => (
                  <circle
                    key={s.bucket}
                    cx="60"
                    cy="60"
                    r={CIRCLE_R}
                    fill="none"
                    stroke={PRIORITY_BUCKET_COLOR[s.bucket]}
                    strokeWidth="16"
                    strokeDasharray={`${s.length} ${CIRCUMFERENCE - s.length}`}
                    strokeDashoffset={s.offset}
                    transform="rotate(-90 60 60)"
                  />
                ))}
              <text x="60" y="56" textAnchor="middle" fontFamily="JetBrains Mono" fontSize="20" fontWeight="700" fill="#14213D">
                {submissions.length}
              </text>
              <text x="60" y="72" textAnchor="middle" fontFamily="Pretendard" fontSize="9" fill="#66708A">
                총 건수
              </text>
            </svg>
            <div style={{ fontSize: 12.5, lineHeight: 2.1 }}>
              {priorityBuckets.map(({ bucket, count }) => (
                <div key={bucket}>
                  <span className={`badge ${bucket}`} style={{ marginRight: 8 }}>
                    {PRIORITY_BUCKET_LABEL[bucket]}
                  </span>
                  {count}건
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="card" style={{ marginTop: 18 }}>
        <h2 className="section-title">처리 지연 건 (익일 오전 9시 초과)</h2>
        {delayedItems.length === 0 ? (
          <div className="empty-state">지연된 문의가 없습니다.</div>
        ) : (
          <table>
            <tbody>
              <tr>
                <th>문의 ID</th>
                <th>문의 내용</th>
                <th>유형</th>
                <th>담당 부서</th>
                <th>경과 시간</th>
                <th>우선순위</th>
              </tr>
              {delayedItems.map((item) => (
                <tr key={item.id}>
                  <td className="mono">{item.id.slice(0, 8)}</td>
                  <td>{item.raw_text.length > 40 ? `${item.raw_text.slice(0, 40)}…` : item.raw_text}</td>
                  <td>{item.inquiry_type}</td>
                  <td>{item.department}</td>
                  <td>{formatElapsed(item.submitted_at)}</td>
                  <td>
                    <span className={`badge ${priorityBadgeClass(item.priority)}`}>{item.priority}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
