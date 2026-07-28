// 정적 목업 화면. 대시보드 통계/그래프/지연 목록은 백엔드에 대응하는 API가 아직
// 없어서(집계·이력 저장 기능 자체가 없음), 사용자 요청에 따라 제공된 디자인의
// 예시 수치를 그대로 보여준다 — 실제 운영 데이터가 아니다.
export default function DashboardView() {
  return (
    <div className="view" id="view-dashboard">
      <h2 className="section-title">오늘의 처리 현황</h2>
      <div className="grid cols-4" style={{ marginBottom: 18 }}>
        <div className="card stat-card">
          <div className="stat-label">총 접수 건수</div>
          <div className="stat-value">248</div>
          <div className="stat-delta up">▲ 12건 (전일 대비)</div>
        </div>
        <div className="card stat-card">
          <div className="stat-label">처리 지연 건수</div>
          <div className="stat-value">17</div>
          <div className="stat-delta up">▲ 3건 · 24시간 초과</div>
        </div>
        <div className="card stat-card">
          <div className="stat-label">우선순위 高</div>
          <div className="stat-value">9</div>
          <div className="stat-delta down">▼ 2건 (전일 대비)</div>
        </div>
        <div className="card stat-card">
          <div className="stat-label">평균 처리 시간</div>
          <div className="stat-value">
            3.4<span style={{ fontSize: 14, color: 'var(--text-dim)' }}>시간</span>
          </div>
          <div className="stat-delta down">▼ 0.6시간 단축</div>
        </div>
      </div>

      <div className="grid cols-2">
        <div className="card">
          <h2 className="section-title">유형별 접수 현황</h2>
          <svg viewBox="0 0 420 190" width="100%" height="190">
            <g fontFamily="JetBrains Mono" fontSize="10" fill="#66708A">
              <rect x="30" y="30" width="46" height="120" rx="5" fill="#0E8C86" />
              <rect x="96" y="70" width="46" height="80" rx="5" fill="#59B7B1" />
              <rect x="162" y="50" width="46" height="100" rx="5" fill="#D98C2B" />
              <rect x="228" y="95" width="46" height="55" rx="5" fill="#C6494A" />
              <rect x="294" y="110" width="46" height="40" rx="5" fill="#B9C0D4" />
              <text x="53" y="168" textAnchor="middle">수강신청</text>
              <text x="119" y="168" textAnchor="middle">장학금</text>
              <text x="185" y="168" textAnchor="middle">시설/민원</text>
              <text x="251" y="168" textAnchor="middle">증명서</text>
              <text x="317" y="168" textAnchor="middle">기타</text>
              <text x="53" y="24" textAnchor="middle" fill="#14213D" fontWeight="600">102</text>
              <text x="119" y="64" textAnchor="middle" fill="#14213D" fontWeight="600">64</text>
              <text x="185" y="44" textAnchor="middle" fill="#14213D" fontWeight="600">86</text>
              <text x="251" y="89" textAnchor="middle" fill="#14213D" fontWeight="600">41</text>
              <text x="317" y="104" textAnchor="middle" fill="#14213D" fontWeight="600">28</text>
            </g>
          </svg>
        </div>

        <div className="card">
          <h2 className="section-title">우선순위 분포</h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
            <svg viewBox="0 0 120 120" width="130" height="130">
              <circle cx="60" cy="60" r="45" fill="none" stroke="#EDEFF4" strokeWidth="16" />
              <circle
                cx="60" cy="60" r="45" fill="none" stroke="#C6494A" strokeWidth="16"
                strokeDasharray="42 240" strokeDashoffset="0" transform="rotate(-90 60 60)"
              />
              <circle
                cx="60" cy="60" r="45" fill="none" stroke="#D98C2B" strokeWidth="16"
                strokeDasharray="90 240" strokeDashoffset="-42" transform="rotate(-90 60 60)"
              />
              <circle
                cx="60" cy="60" r="45" fill="none" stroke="#0E8C86" strokeWidth="16"
                strokeDasharray="150 240" strokeDashoffset="-132" transform="rotate(-90 60 60)"
              />
              <text x="60" y="56" textAnchor="middle" fontFamily="JetBrains Mono" fontSize="20" fontWeight="700" fill="#14213D">248</text>
              <text x="60" y="72" textAnchor="middle" fontFamily="Pretendard" fontSize="9" fill="#66708A">총 건수</text>
            </svg>
            <div style={{ fontSize: 12.5, lineHeight: 2.1 }}>
              <div><span className="badge high" style={{ marginRight: 8 }}>高</span>9건 · 즉시 대응 필요</div>
              <div><span className="badge mid" style={{ marginRight: 8 }}>中</span>60건 · 당일 처리</div>
              <div><span className="badge low" style={{ marginRight: 8 }}>低</span>179건 · 순차 처리</div>
            </div>
          </div>
        </div>
      </div>

      <div className="card" style={{ marginTop: 18 }}>
        <h2 className="section-title">처리 지연 건 (24시간 초과)</h2>
        <table>
          <tbody>
            <tr><th>문의 ID</th><th>제목</th><th>유형</th><th>담당 부서</th><th>경과 시간</th><th>우선순위</th></tr>
            <tr><td className="mono">INQ-3391</td><td>수강신청 정정기간 오류 문의</td><td>수강신청</td><td>학사지원팀</td><td>29시간</td><td><span className="badge high">高</span></td></tr>
            <tr><td className="mono">INQ-3388</td><td>장학금 지급 일정 확인 요청</td><td>장학금</td><td>학생지원팀</td><td>26시간</td><td><span className="badge mid">中</span></td></tr>
            <tr><td className="mono">INQ-3375</td><td>기숙사 시설 파손 신고</td><td>시설/민원</td><td>시설관리팀</td><td>25시간</td><td><span className="badge mid">中</span></td></tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}
