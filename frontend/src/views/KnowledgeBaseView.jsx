// 정적 목업 화면. 문서 업로드/임베딩 상태 관리 API가 아직 없어서, 사용자 요청에
// 따라 제공된 디자인의 예시 문서 목록을 그대로 보여준다 — 검색창·버튼은 장식용이다.
export default function KnowledgeBaseView() {
  return (
    <div className="view" id="view-kb">
      <div className="kb-toolbar">
        <div className="search-box">
          🔍 <input type="text" placeholder="문서명으로 검색" />
        </div>
        <button className="btn btn-teal" type="button">+ 문서 업로드</button>
      </div>
      <div className="card">
        <table>
          <tbody>
            <tr><th>문서</th><th>분류</th><th>업로드일</th><th>임베딩 상태</th><th></th></tr>
            <tr>
              <td>
                <div className="doc-name-cell">
                  <div className="doc-icon">PDF</div>
                  <div>
                    <div>수강신청_FAQ_2026.pdf</div>
                    <div className="doc-meta">1.2MB · 문단 48개</div>
                  </div>
                </div>
              </td>
              <td>FAQ</td><td>2026-03-02</td>
              <td><span className="badge low">임베딩 완료</span></td>
              <td><button className="btn btn-ghost" style={{ padding: '6px 12px' }} type="button">재처리</button></td>
            </tr>
            <tr>
              <td>
                <div className="doc-name-cell">
                  <div className="doc-icon">PDF</div>
                  <div>
                    <div>학사운영규정_전문.pdf</div>
                    <div className="doc-meta">4.8MB · 문단 212개</div>
                  </div>
                </div>
              </td>
              <td>규정</td><td>2025-09-11</td>
              <td><span className="badge low">임베딩 완료</span></td>
              <td><button className="btn btn-ghost" style={{ padding: '6px 12px' }} type="button">재처리</button></td>
            </tr>
            <tr>
              <td>
                <div className="doc-name-cell">
                  <div className="doc-icon">DOC</div>
                  <div>
                    <div>수강신청_트러블슈팅.docx</div>
                    <div className="doc-meta">640KB · 문단 36개</div>
                  </div>
                </div>
              </td>
              <td>매뉴얼</td><td>2026-01-20</td>
              <td><span className="badge mid">임베딩 중 (67%)</span></td>
              <td><button className="btn btn-ghost" style={{ padding: '6px 12px' }} type="button" disabled>대기</button></td>
            </tr>
            <tr>
              <td>
                <div className="doc-name-cell">
                  <div className="doc-icon">PDF</div>
                  <div>
                    <div>2026학년도_2학기_공지사항.pdf</div>
                    <div className="doc-meta">920KB · 문단 19개</div>
                  </div>
                </div>
              </td>
              <td>공지사항</td><td>2026-07-20</td>
              <td><span className="badge high">임베딩 실패</span></td>
              <td><button className="btn btn-primary" style={{ padding: '6px 12px' }} type="button">재시도</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}
