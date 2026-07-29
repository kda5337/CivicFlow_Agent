import { Fragment, useEffect, useState } from 'react'

const KNOWLEDGE_BASE_URL = 'http://localhost:8000/knowledge-base'

const inputStyle = {
  width: '100%',
  border: '1px solid var(--line)',
  borderRadius: 8,
  padding: '8px 10px',
  fontSize: 13,
  fontFamily: 'inherit',
  boxSizing: 'border-box',
}

// 실제 GET /knowledge-base(backend/app/rag/knowledge_base.py)를 그대로 보여준다.
// RAG 근거로 쓰이는 FAQ 출처(Supabase 테이블 11개)마다 실제 행 수와 검색용 임베딩
// (chroma_merged_faq) 건수를 나란히 보여주고, 둘이 어긋나면 "재처리"로 그 출처만
// 다시 임베딩할 수 있다. "상세보기"를 누르면 그 출처의 실제 질문/답변을 펼쳐서
// 추가/수정/삭제까지 할 수 있다(수정/삭제는 이전 값을 남기지 않고 바로 덮어쓴다).
// 각 변경은 테이블 전체가 아니라 그 항목 하나만 Chroma에 반영한다(백엔드
// create_item/update_item/delete_item 참고) — 원본 데이터셋 자체의 수집은 여전히
// ingest_*.py 스크립트가 담당한다.
export default function KnowledgeBaseView() {
  const [sources, setSources] = useState(null)
  const [error, setError] = useState(null)
  const [reprocessingTable, setReprocessingTable] = useState(null)
  const [reprocessError, setReprocessError] = useState(null)

  const [expandedTable, setExpandedTable] = useState(null)
  // table -> { items, error } | undefined. 한 번 불러온 출처는 다시 펼칠 때 재요청하지
  // 않고 캐시된 값을 그대로 보여준다("새로고침"을 누르면 전체가 초기화된다).
  const [itemsByTable, setItemsByTable] = useState({})
  const [loadingItemsTable, setLoadingItemsTable] = useState(null)

  // editing: { table, id } | null. id는 기존 항목 수정 시 숫자, 새 항목 추가 폼일 때는
  // 'new'. 한 번에 한 항목만 편집/추가할 수 있다.
  const [editing, setEditing] = useState(null)
  const [draft, setDraft] = useState({ question: '', answer: '' })
  const [savingKey, setSavingKey] = useState(null)
  const [itemActionError, setItemActionError] = useState(null)

  const load = () => {
    setError(null)
    fetch(KNOWLEDGE_BASE_URL)
      .then((response) => {
        if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
        return response.json()
      })
      .then(setSources)
      .catch((err) => setError(err.message))
    setExpandedTable(null)
    setItemsByTable({})
    setEditing(null)
  }

  useEffect(() => {
    load()
  }, [])

  const handleReprocess = async (table) => {
    setReprocessingTable(table)
    setReprocessError(null)
    try {
      const response = await fetch(`${KNOWLEDGE_BASE_URL}/${table}/reprocess`, { method: 'POST' })
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
      const updated = await response.json()
      setSources((prev) => prev.map((source) => (source.table === table ? updated : source)))
    } catch (err) {
      setReprocessError(`${table}: ${err.message}`)
    } finally {
      setReprocessingTable(null)
    }
  }

  const handleToggleDetail = (table) => {
    setEditing(null)
    if (expandedTable === table) {
      setExpandedTable(null)
      return
    }
    setExpandedTable(table)
    if (itemsByTable[table]) return

    setLoadingItemsTable(table)
    fetch(`${KNOWLEDGE_BASE_URL}/${table}/items`)
      .then((response) => {
        if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
        return response.json()
      })
      .then((items) => setItemsByTable((prev) => ({ ...prev, [table]: { items, error: null } })))
      .catch((err) => setItemsByTable((prev) => ({ ...prev, [table]: { items: null, error: err.message } })))
      .finally(() => setLoadingItemsTable(null))
  }

  // 추가/수정 한 건이 반영됐을 때, 목록 전체를 다시 불러오지 않고 이 출처의
  // Supabase/임베딩 건수만 그 자리에서 맞춰준다(둘은 항상 같이 늘고 줄어든다).
  const adjustSourceCount = (table, delta) => {
    setSources((prev) =>
      prev.map((source) =>
        source.table === table
          ? {
              ...source,
              row_count: source.row_count + delta,
              embedded_count: source.embedded_count + delta,
              in_sync: true,
            }
          : source
      )
    )
  }

  const startAdd = (table) => {
    setItemActionError(null)
    setEditing({ table, id: 'new' })
    setDraft({ question: '', answer: '' })
  }

  const startEdit = (table, item) => {
    setItemActionError(null)
    setEditing({ table, id: item.id })
    setDraft({ question: item.question, answer: item.answer })
  }

  const cancelEdit = () => {
    setEditing(null)
    setItemActionError(null)
  }

  const handleSave = async () => {
    if (!draft.question.trim() || !draft.answer.trim()) {
      setItemActionError('질문과 답변을 모두 입력해 주세요.')
      return
    }
    const { table, id } = editing
    const isNew = id === 'new'
    const key = `${table}:${id}`
    setSavingKey(key)
    setItemActionError(null)
    try {
      const response = await fetch(
        isNew ? `${KNOWLEDGE_BASE_URL}/${table}/items` : `${KNOWLEDGE_BASE_URL}/${table}/items/${id}`,
        {
          method: isNew ? 'POST' : 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: draft.question.trim(), answer: draft.answer.trim() }),
        }
      )
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
      const saved = await response.json()
      setItemsByTable((prev) => {
        const current = prev[table]?.items || []
        const nextItems = isNew
          ? [...current, saved]
          : current.map((item) => (item.id === saved.id ? saved : item))
        return { ...prev, [table]: { items: nextItems, error: null } }
      })
      if (isNew) adjustSourceCount(table, 1)
      setEditing(null)
    } catch (err) {
      setItemActionError(err.message)
    } finally {
      setSavingKey(null)
    }
  }

  const handleDelete = async (table, item) => {
    if (!window.confirm('이 항목을 삭제하시겠습니까? 되돌릴 수 없습니다.')) return
    const key = `${table}:${item.id}`
    setSavingKey(key)
    setItemActionError(null)
    try {
      const response = await fetch(`${KNOWLEDGE_BASE_URL}/${table}/items/${item.id}`, { method: 'DELETE' })
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
      setItemsByTable((prev) => ({
        ...prev,
        [table]: { items: (prev[table]?.items || []).filter((i) => i.id !== item.id), error: null },
      }))
      adjustSourceCount(table, -1)
      if (editing?.table === table && editing?.id === item.id) setEditing(null)
    } catch (err) {
      setItemActionError(err.message)
    } finally {
      setSavingKey(null)
    }
  }

  return (
    <div className="view" id="view-kb">
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <h2 className="section-title" style={{ margin: 0 }}>
            지식베이스 관리 {sources ? `(${sources.length}개 출처)` : ''}
          </h2>
          <button className="btn btn-ghost" type="button" onClick={load}>
            새로고침
          </button>
        </div>
        <p style={{ fontSize: 12.5, color: 'var(--text-dim)', marginTop: -8, marginBottom: 16 }}>
          답변 생성에 쓰이는 RAG 근거 문서 출처별 현황입니다. "상세보기"에서 질문/답변을 직접 추가·수정·삭제할
          수 있고, Supabase 실제 건수와 검색용 임베딩 건수가 다르면 "재처리"로 그 출처만 다시 임베딩할 수 있습니다.
        </p>

        {error && <div className="error-banner">목록을 불러오지 못했습니다: {error}</div>}
        {reprocessError && <div className="error-banner">재처리 실패: {reprocessError}</div>}

        {sources && sources.length > 0 && (
          <table>
            <tbody>
              <tr>
                <th></th>
                <th>출처</th>
                <th>Supabase 건수</th>
                <th>임베딩 건수</th>
                <th>상태</th>
                <th></th>
              </tr>
              {sources.map((source) => {
                const isOpen = expandedTable === source.table
                const cached = itemsByTable[source.table]
                const isAddingHere = editing?.table === source.table && editing?.id === 'new'
                return (
                  <Fragment key={source.table}>
                    <tr>
                      <td>
                        <button
                          className="btn btn-ghost"
                          style={{ padding: '4px 8px' }}
                          type="button"
                          onClick={() => handleToggleDetail(source.table)}
                        >
                          {isOpen ? '▾' : '▸'}
                        </button>
                      </td>
                      <td>
                        <div className="doc-name-cell">
                          <div className="doc-icon">FAQ</div>
                          <div>
                            <div>{source.label}</div>
                            <div className="doc-meta" style={{ fontFamily: 'var(--mono)' }}>
                              {source.table}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="mono">{source.row_count}건</td>
                      <td className="mono">{source.embedded_count}건</td>
                      <td>
                        {source.in_sync ? (
                          <span className="badge low">동기화됨</span>
                        ) : (
                          <span className="badge high">재처리 필요</span>
                        )}
                      </td>
                      <td style={{ display: 'flex', gap: 8, whiteSpace: 'nowrap' }}>
                        <button
                          className="btn btn-ghost"
                          style={{ padding: '6px 12px' }}
                          type="button"
                          onClick={() => handleToggleDetail(source.table)}
                        >
                          {isOpen ? '접기' : '상세보기'}
                        </button>
                        <button
                          className="btn btn-ghost"
                          style={{ padding: '6px 12px' }}
                          type="button"
                          disabled={reprocessingTable !== null}
                          onClick={() => handleReprocess(source.table)}
                        >
                          {reprocessingTable === source.table ? (
                            <>
                              <span className="spinner" />
                              재처리 중
                            </>
                          ) : (
                            '재처리'
                          )}
                        </button>
                      </td>
                    </tr>
                    {isOpen && (
                      <tr>
                        <td></td>
                        <td colSpan={5} style={{ padding: '4px 0 18px' }}>
                          {loadingItemsTable === source.table && (
                            <div className="empty-state">불러오는 중...</div>
                          )}
                          {cached?.error && (
                            <div className="error-banner">항목을 불러오지 못했습니다: {cached.error}</div>
                          )}
                          {cached?.items && (
                            <div
                              className="card"
                              style={{ background: 'var(--bg)', maxHeight: 460, overflowY: 'auto' }}
                            >
                              <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
                                <button
                                  className="btn btn-teal"
                                  style={{ padding: '6px 12px', fontSize: 12.5 }}
                                  type="button"
                                  onClick={() => startAdd(source.table)}
                                  disabled={editing !== null}
                                >
                                  + 항목 추가
                                </button>
                              </div>

                              {itemActionError && (
                                <div className="error-banner">{itemActionError}</div>
                              )}

                              {isAddingHere && (
                                <div
                                  style={{
                                    border: '1px dashed var(--line)',
                                    borderRadius: 9,
                                    padding: 12,
                                    marginBottom: 14,
                                    display: 'flex',
                                    flexDirection: 'column',
                                    gap: 8,
                                  }}
                                >
                                  <textarea
                                    style={{ ...inputStyle, minHeight: 44 }}
                                    placeholder="질문"
                                    value={draft.question}
                                    onChange={(e) => setDraft({ ...draft, question: e.target.value })}
                                  />
                                  <textarea
                                    style={{ ...inputStyle, minHeight: 70 }}
                                    placeholder="답변"
                                    value={draft.answer}
                                    onChange={(e) => setDraft({ ...draft, answer: e.target.value })}
                                  />
                                  <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                                    <button className="btn btn-ghost" type="button" onClick={cancelEdit}>
                                      취소
                                    </button>
                                    <button
                                      className="btn btn-primary"
                                      type="button"
                                      disabled={savingKey === `${source.table}:new`}
                                      onClick={handleSave}
                                    >
                                      {savingKey === `${source.table}:new` ? '저장 중...' : '저장'}
                                    </button>
                                  </div>
                                </div>
                              )}

                              {cached.items.length === 0 && !isAddingHere ? (
                                <div className="empty-state">데이터가 없습니다.</div>
                              ) : (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                                  {cached.items.map((item) => {
                                    const isEditingHere =
                                      editing?.table === source.table && editing?.id === item.id
                                    const key = `${source.table}:${item.id}`
                                    return (
                                      <div
                                        key={item.id}
                                        style={{ borderBottom: '1px solid var(--line)', paddingBottom: 12 }}
                                      >
                                        {isEditingHere ? (
                                          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                                            <textarea
                                              style={{ ...inputStyle, minHeight: 44 }}
                                              value={draft.question}
                                              onChange={(e) => setDraft({ ...draft, question: e.target.value })}
                                            />
                                            <textarea
                                              style={{ ...inputStyle, minHeight: 70 }}
                                              value={draft.answer}
                                              onChange={(e) => setDraft({ ...draft, answer: e.target.value })}
                                            />
                                            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                                              <button className="btn btn-ghost" type="button" onClick={cancelEdit}>
                                                취소
                                              </button>
                                              <button
                                                className="btn btn-primary"
                                                type="button"
                                                disabled={savingKey === key}
                                                onClick={handleSave}
                                              >
                                                {savingKey === key ? '저장 중...' : '저장'}
                                              </button>
                                            </div>
                                          </div>
                                        ) : (
                                          <>
                                            <div
                                              style={{
                                                display: 'flex',
                                                justifyContent: 'space-between',
                                                gap: 12,
                                                alignItems: 'flex-start',
                                              }}
                                            >
                                              <div style={{ fontSize: 13.5, fontWeight: 700, marginBottom: 4 }}>
                                                Q. {item.question}
                                              </div>
                                              <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                                                <button
                                                  className="btn btn-ghost"
                                                  style={{ padding: '4px 10px', fontSize: 12 }}
                                                  type="button"
                                                  disabled={editing !== null || savingKey === key}
                                                  onClick={() => startEdit(source.table, item)}
                                                >
                                                  수정
                                                </button>
                                                <button
                                                  className="btn btn-ghost"
                                                  style={{ padding: '4px 10px', fontSize: 12, color: 'var(--red)' }}
                                                  type="button"
                                                  disabled={editing !== null || savingKey === key}
                                                  onClick={() => handleDelete(source.table, item)}
                                                >
                                                  {savingKey === key ? '삭제 중...' : '삭제'}
                                                </button>
                                              </div>
                                            </div>
                                            <div
                                              style={{
                                                fontSize: 13,
                                                color: 'var(--text-dim)',
                                                whiteSpace: 'pre-wrap',
                                                lineHeight: 1.6,
                                              }}
                                            >
                                              A. {item.answer}
                                            </div>
                                          </>
                                        )}
                                      </div>
                                    )
                                  })}
                                </div>
                              )}
                            </div>
                          )}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
