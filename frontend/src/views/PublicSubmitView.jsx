import { useEffect, useRef, useState } from "react"
import {
  AlertTriangle,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  FileText,
  Inbox,
  Sparkles,
} from "lucide-react"
import { API_BASE_URL } from "../config.js"

// 실제 시민(사용자)이 접속하는 독립 페이지 (/submit). 내부 담당자용 화면(Sidebar/
// Topbar/Pipeline)과 완전히 분리되어 있다 — App.jsx가 경로를 보고 이 컴포넌트만
// 단독으로 렌더링한다.
//
// 다섯 개 탭 전부 실제 백엔드(citizen_submissions) 데이터만 쓴다. "문의 등록" 직후
// 서버가 바로 classify_node+rules_node를 돌려 문의유형/담당부서/우선순위/감정상태를
// 채우므로(status가 '검토중'이 됨), "문의 유형 자동 확인"/"처리 상태 조회"는 이미
// 저장된 그 결과를 보여주는 화면이지 프론트에서 흉내낸 가짜 분류가 아니다. 담당부서를
// 고치는 버튼은 담당자 내부 화면(AI 분석 결과)에만 있고, 여기서는 결과만 보여준다.
const SUBMIT_URL = `${API_BASE_URL}/submissions`
const VISITOR_NAME_KEY = "civicflow_visitor_name"
const SEEN_ANSWERS_KEY_PREFIX = "civicflow_seen_answers_"
// 페이지를 켜둔 채로 있어도 담당자가 답변을 완료하면 배지가 뜨도록, 이 간격으로
// 목록을 조용히 다시 불러온다 — 사용자가 새로고침을 직접 할 필요가 없게 하기 위함.
const POLL_INTERVAL_MS = 20000

function loadSeenAnswerIds(name) {
  try {
    return new Set(JSON.parse(localStorage.getItem(SEEN_ANSWERS_KEY_PREFIX + name) || "[]"))
  } catch {
    return new Set()
  }
}

function saveSeenAnswerIds(name, ids) {
  localStorage.setItem(SEEN_ANSWERS_KEY_PREFIX + name, JSON.stringify([...ids]))
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

// 캐시로 처리돼도 화면 단계(적절성 확인 중 -> 분류 중)는 그대로 다 보여준다 — 다만 그
// 뒤에 있는 실제 작업이 LLM 호출 없이 캐시 조회만이라 순식간에 끝나버리면 화면이
// 깜빡이듯 지나가 버린다. 최소 시간만큼은 그 화면에 머무르도록 보장해, 사용자에게는
// 여전히 "확인 -> 분류 -> 접수 완료"가 순서대로 진행되는 것처럼 보이게 한다.
const CACHE_STEP_MIN_MS = 600

async function withMinDelay(promise, ms) {
  const [result] = await Promise.all([promise, sleep(ms)])
  return result
}

const T = {
  navy900: "#0E1826",
  navy700: "#1D2E48",
  teal: "#14705C",
  tealSoft: "#E1F5EE",
  tealText: "#0F6E56",
  ink: "#1B2635",
  sub: "#5B6472",
  muted: "#8B93A0",
  border: "#E3E5EA",
  page: "#F6F7F9",
  danger: "#A32D2D",
}

const STATUS_STYLE = {
  접수완료: { bg: "#E9EEF5", fg: "#3D4C63", icon: Inbox },
  검토중: { bg: "#FDF1DC", fg: "#8A5A12", icon: Clock },
  답변완료: { bg: "#E1F5EE", fg: "#0F6E56", icon: CheckCircle2 },
}

const card = { background: "#fff", border: `1px solid ${T.border}`, borderRadius: 14, padding: 22 }
const inputStyle = {
  width: "100%",
  border: `1px solid ${T.border}`,
  borderRadius: 9,
  padding: "10px 12px",
  fontSize: 14.5,
  fontFamily: "inherit",
  color: T.ink,
  background: "#FBFCFD",
  boxSizing: "border-box",
}
const primaryBtn = {
  background: T.navy900,
  color: "#fff",
  border: "none",
  borderRadius: 9,
  padding: "11px 20px",
  fontSize: 14.5,
  fontWeight: 500,
  cursor: "pointer",
  display: "inline-flex",
  alignItems: "center",
  gap: 8,
}
const secondaryBtn = {
  background: "#fff",
  color: T.sub,
  border: `1px solid ${T.border}`,
  borderRadius: 9,
  padding: "11px 18px",
  fontSize: 14.5,
  fontWeight: 500,
  cursor: "pointer",
}

function Row({ label, value }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
      <span style={{ color: T.sub }}>{label}</span>
      <span style={{ color: T.ink, fontWeight: 500, textAlign: "right" }}>{value}</span>
    </div>
  )
}

function StatusPill({ status }) {
  const s = STATUS_STYLE[status] || STATUS_STYLE["접수완료"]
  const Icon = s.icon
  return (
    <span
      style={{
        display: "inline-flex", alignItems: "center", gap: 6, background: s.bg, color: s.fg,
        padding: "4px 11px", borderRadius: 999, fontSize: 12.5, fontWeight: 500, whiteSpace: "nowrap",
      }}
    >
      <Icon size={13} strokeWidth={2.2} />
      {status}
    </span>
  )
}

function EmptyState({ text }) {
  return (
    <div style={{ ...card, textAlign: "center", color: T.muted, padding: "40px 20px", borderStyle: "dashed" }}>
      {text}
    </div>
  )
}

function PageHead({ title, desc }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24, gap: 16, flexWrap: "wrap" }}>
      <div>
        <h1 style={{ fontSize: 21, fontWeight: 500, color: T.ink, margin: 0 }}>{title}</h1>
        {desc && <p style={{ color: T.sub, fontSize: 13.5, marginTop: 6, maxWidth: 560 }}>{desc}</p>}
      </div>
    </div>
  )
}

function Stepper({ steps, current }) {
  return (
    <div style={{ display: "flex", alignItems: "center", marginBottom: 26 }}>
      {steps.map((s, i) => {
        const n = i + 1
        const done = n < current
        const active = n === current
        return (
          <div key={s} style={{ display: "flex", alignItems: "center", flex: i < steps.length - 1 ? 1 : "0 0 auto" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
              <div
                style={{
                  width: 28, height: 28, borderRadius: "50%", flexShrink: 0, display: "flex",
                  alignItems: "center", justifyContent: "center", fontSize: 12.5, fontWeight: 500,
                  background: done || active ? T.teal : "#fff", color: done || active ? "#fff" : T.muted,
                  border: `1.5px solid ${done || active ? T.teal : T.border}`,
                }}
              >
                {done ? <Check size={14} /> : n}
              </div>
              <span style={{ fontSize: 13.5, fontWeight: 500, color: active ? T.ink : T.muted, whiteSpace: "nowrap" }}>{s}</span>
            </div>
            {i < steps.length - 1 && <div style={{ flex: 1, height: 1, background: done ? T.teal : T.border, margin: "0 14px" }} />}
          </div>
        )
      })}
    </div>
  )
}

function formatTime(iso) {
  return new Date(iso).toLocaleString("ko-KR", {
    year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
  })
}

function truncate(text, n) {
  return text.length > n ? `${text.slice(0, n)}…` : text
}

const PHONE_PATTERN = /^010-\d{4}-\d{4}$/

// 숫자만 남기고 011자리까지 잘라 010-0000-0000 형태로 자동 하이픈을 붙인다 —
// 입력 중에는 자유롭게 지우고 다시 칠 수 있게, 커서 위치는 신경 쓰지 않고
// 값 전체를 매번 다시 포맷한다.
function formatPhoneInput(raw) {
  const digits = raw.replace(/\D/g, "").slice(0, 11)
  if (digits.length <= 3) return digits
  if (digits.length <= 7) return `${digits.slice(0, 3)}-${digits.slice(3)}`
  return `${digits.slice(0, 3)}-${digits.slice(3, 7)}-${digits.slice(7)}`
}

/* ---------------- 이름 게이트 ---------------- */
function NameGate({ onConfirm }) {
  const [nameInput, setNameInput] = useState("")
  return (
    <div
      style={{
        minHeight: "100vh", display: "flex", alignItems: "flex-start", justifyContent: "center",
        background: `linear-gradient(180deg, ${T.navy900}, #16233A)`, padding: "48px 16px",
      }}
    >
      <div style={{ width: "100%", maxWidth: 420, background: "#fff", borderRadius: 16, padding: "32px 30px", boxShadow: "0 20px 60px rgba(15,27,51,.35)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 24 }}>
          <div style={{ width: 38, height: 38, borderRadius: 9, background: T.teal, color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 500, fontSize: 14 }}>
            CF
          </div>
          <div style={{ fontWeight: 700, fontSize: 13.5, color: T.sub }}>CivicFlow 민원·문의 접수</div>
        </div>
        <form
          onSubmit={(event) => {
            event.preventDefault()
            const trimmed = nameInput.trim()
            if (!trimmed) return
            onConfirm(trimmed)
          }}
        >
          <h1 style={{ fontSize: 19, fontWeight: 700, color: T.ink, margin: "0 0 6px" }}>먼저 이름을 알려주세요</h1>
          <p style={{ fontSize: 12.5, color: T.sub, margin: "0 0 20px", lineHeight: 1.6 }}>
            이름으로 이전에 남기신 문의 내역을 함께 보여드립니다.
          </p>
          <label style={{ fontSize: 13, fontWeight: 500, color: T.sub }}>
            이름
            <input
              style={{ ...inputStyle, marginTop: 6 }}
              placeholder="홍길동"
              value={nameInput}
              onChange={(event) => setNameInput(event.target.value)}
              autoFocus
            />
          </label>
          <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 20 }}>
            <button style={primaryBtn} type="submit" disabled={!nameInput.trim()}>
              다음 <ArrowRight size={15} />
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

/* ---------------- 탭 1. 문의 등록 ---------------- */
function RegisterTab({ visitorName, onSubmitted }) {
  const [title, setTitle] = useState("")
  const [content, setContent] = useState("")
  const [contact, setContact] = useState("")
  const [error, setError] = useState("")
  // intake_node가 "민원·문의가 아님"으로 판단해 422로 거부된 경우의 사유. 일반
  // 오류(error)와 구분해서, 재작성을 유도하는 안내로 보여준다.
  const [rejection, setRejection] = useState("")
  const [result, setResult] = useState(null)
  // 등록 버튼을 누른 뒤의 단계: form(작성) -> checking(적절성 검사 중, 실제로
  // POST /submissions/check-relevance가 도는 중) -> ok(적절함이 확인되어 체크 표시,
  // 잠깐 보여주는 연출) -> classifying(분류·저장 중, 실제로 POST /submissions가 도는
  // 중) -> result(분류 결과 표시). checking과 classifying은 각각 별도의 요청 하나에
  // 대응해서, 화면이 실제 백엔드 진행 상황과 같은 순서로 넘어간다.
  const [phase, setPhase] = useState("form")
  const okTimerRef = useRef(null)
  // 단계 전환 타이머가 끝난 뒤 컴포넌트가 이미 unmount됐으면(다른 탭으로 이동 등)
  // setState를 호출하지 않기 위한 가드.
  const unmountedRef = useRef(false)

  useEffect(() => {
    // StrictMode가 개발 모드에서 마운트 -> 정리 -> 재마운트를 한 번 시뮬레이션하는데,
    // 이때 아래 cleanup만 있으면 재마운트 후에도 true로 남아 그 뒤 모든 요청이
    // 조용히 무시된다 — 그래서 마운트될 때마다 false로 되돌려준다.
    unmountedRef.current = false
    return () => {
      unmountedRef.current = true
      clearTimeout(okTimerRef.current)
    }
  }, [])

  const handleSubmit = async () => {
    if (!content.trim() || !contact.trim()) {
      setError("연락처와 문의 내용을 입력해 주세요.")
      return
    }
    if (!PHONE_PATTERN.test(contact.trim())) {
      setError("연락처는 010-0000-0000 형식으로 입력해 주세요.")
      return
    }
    setError("")
    setRejection("")
    setPhase("checking")
    const rawText = title.trim() ? `${title.trim()}\n\n${content.trim()}` : content.trim()
    try {
      // 캐시 히트 여부를 먼저 조용히 확인한다 — DB에는 아무것도 안 쓰고, 이 결과에
      // 따라 실제 관련성 판별(LLM 호출)을 할지 건너뛸지만 정한다. "적절성 확인 중"
      // 화면 자체는 히트/미스와 무관하게 그대로 보여준다(최소 노출 시간만 보장).
      const cacheCheckResponse = await withMinDelay(
        fetch(`${SUBMIT_URL}/cache-check`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ raw_text: rawText }),
        }),
        CACHE_STEP_MIN_MS
      )
      const cacheHit = cacheCheckResponse.ok && (await cacheCheckResponse.json()).cache_hit
      if (unmountedRef.current) return

      if (!cacheHit) {
        const relevanceResponse = await fetch(`${SUBMIT_URL}/check-relevance`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ raw_text: rawText }),
        })
        if (!relevanceResponse.ok) throw new Error(`${relevanceResponse.status} ${relevanceResponse.statusText}`)
        const relevance = await relevanceResponse.json()
        if (unmountedRef.current) return

        if (!relevance.관련여부) {
          setRejection(relevance.판단근거 || "민원·문의 내용으로 확인되지 않았습니다.")
          setPhase("form")
          return
        }
      }

      // "적절함" 확인을 사용자가 눈으로 볼 수 있게 잠깐 보여준 뒤 분류 단계로 넘어간다.
      setPhase("ok")
      okTimerRef.current = setTimeout(async () => {
        if (unmountedRef.current) return
        setPhase("classifying")
        try {
          const submitRequest = fetch(SUBMIT_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              name: visitorName,
              contact: contact.trim(),
              raw_text: rawText,
              skip_relevance_check: true,
            }),
          })
          // 캐시 히트면 분류도 순식간에 끝나 화면이 깜빡이므로, 여기서도 최소 노출
          // 시간을 보장한다. 미스면 실제 분류 LLM 호출이 자체적으로 시간이 걸리니
          // 별도 지연이 필요 없다.
          const response = cacheHit ? await withMinDelay(submitRequest, CACHE_STEP_MIN_MS) : await submitRequest
          if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
          const json = await response.json()
          if (unmountedRef.current) return
          setResult(json)
          setTitle("")
          setContent("")
          setContact("")
          onSubmitted()
          setPhase("result")
        } catch (err) {
          if (unmountedRef.current) return
          setError(`접수 실패: ${err.message}`)
          setPhase("form")
        }
      }, 900)
    } catch (err) {
      if (unmountedRef.current) return
      setError(`접수 실패: ${err.message}`)
      setPhase("form")
    }
  }

  const handleWriteNew = () => {
    setResult(null)
    setPhase("form")
  }

  return (
    <div>
      <PageHead title="문의 등록" desc={`${visitorName}님, 문의를 남겨주시면 자동으로 유형을 확인하고 담당자가 답변드립니다.`} />
      <Stepper
        steps={["작성", "자동 유형 확인", "접수 완료"]}
        current={phase === "form" ? 1 : phase === "result" ? 3 : 2}
      />

      <div style={{ display: "grid", gridTemplateColumns: phase === "form" ? "1fr" : "1.1fr 0.9fr", gap: 24 }} className="cf-grid">
        {phase === "form" && (
          <div style={{ ...card, display: "flex", flexDirection: "column", gap: 14 }}>
            <label style={{ fontSize: 13, fontWeight: 500, color: T.sub }}>
              문의 제목 (선택)
              <input
                style={{ ...inputStyle, marginTop: 6 }}
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="예: 수강신청 정정 시 오류 메시지가 나타납니다"
              />
            </label>
            <label style={{ fontSize: 13, fontWeight: 500, color: T.sub }}>
              문의 내용
              <textarea
                style={{ ...inputStyle, marginTop: 6, minHeight: 150, resize: "vertical" }}
                value={content}
                onChange={(event) => setContent(event.target.value)}
                placeholder="상황을 구체적으로 적어주시면 더 정확하게 분류됩니다."
              />
            </label>
            <label style={{ fontSize: 13, fontWeight: 500, color: T.sub }}>
              연락처
              <input
                style={{ ...inputStyle, marginTop: 6 }}
                value={contact}
                onChange={(event) => setContact(formatPhoneInput(event.target.value))}
                placeholder="010-0000-0000"
                inputMode="numeric"
                maxLength={13}
              />
            </label>
            {rejection && (
              <div style={{ background: "#FDF1DC", color: "#8A5A12", borderRadius: 9, padding: "12px 14px", fontSize: 13, lineHeight: 1.6, display: "flex", gap: 8 }}>
                <AlertTriangle size={15} style={{ flexShrink: 0, marginTop: 1 }} />
                <span>
                  민원·문의 내용으로 확인되지 않아 접수되지 않았습니다.
                  <br />
                  {rejection}
                  <br />
                  처리를 원하시는 민원·문의 내용을 조금 더 구체적으로 적어 다시 시도해 주세요.
                </span>
              </div>
            )}
            {error && (
              <div style={{ color: T.danger, fontSize: 13, display: "flex", gap: 6, alignItems: "center" }}>
                <AlertTriangle size={14} /> {error}
              </div>
            )}
            <div style={{ display: "flex", gap: 10, marginTop: 4, justifyContent: "flex-end" }}>
              <button style={primaryBtn} onClick={handleSubmit}>
                등록하고 유형 확인하기 <ArrowRight size={15} />
              </button>
            </div>
          </div>
        )}

        {phase === "checking" && (
          <div style={{ ...card, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 16, padding: "56px 20px" }}>
            <div
              style={{
                width: 40, height: 40, borderRadius: "50%", border: `3px solid ${T.border}`,
                borderTopColor: T.teal, animation: "cf-spin 0.8s linear infinite",
              }}
            />
            <div style={{ fontSize: 14.5, fontWeight: 500, color: T.ink }}>민원·문의가 맞는지 확인하고 있습니다...</div>
            <div style={{ fontSize: 12.5, color: T.sub }}>적절한 문의로 확인되면 바로 유형 분류를 진행합니다.</div>
          </div>
        )}

        {phase === "ok" && (
          <div style={{ ...card, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 12, padding: "56px 20px" }}>
            <div
              style={{
                width: 54, height: 54, borderRadius: "50%", background: T.tealSoft, color: T.tealText,
                display: "flex", alignItems: "center", justifyContent: "center",
              }}
            >
              <CheckCircle2 size={28} strokeWidth={2.2} />
            </div>
            <div style={{ fontSize: 15, fontWeight: 500, color: T.ink }}>민원·문의로 확인되었습니다</div>
            <div style={{ fontSize: 12.5, color: T.sub }}>이어서 문의 유형을 분류합니다...</div>
          </div>
        )}

        {phase === "classifying" && (
          <div style={{ ...card, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 16, padding: "56px 20px" }}>
            <div style={{ display: "flex", gap: 8 }}>
              {[0, 1, 2].map((i) => (
                <div
                  key={i}
                  style={{
                    width: 12, height: 12, borderRadius: "50%", background: T.teal,
                    animation: "cf-bounce 1s ease-in-out infinite", animationDelay: `${i * 0.15}s`,
                  }}
                />
              ))}
            </div>
            <div style={{ fontSize: 14.5, fontWeight: 500, color: T.ink }}>문의 유형을 분류하고 있습니다...</div>
            <div style={{ fontSize: 12.5, color: T.sub }}>담당 부서를 확인하고 있어요.</div>
          </div>
        )}

        {phase === "result" && result && (
          <div style={{ ...card, display: "flex", gap: 18, alignItems: "flex-start" }}>
            <div
              style={{
                width: 68, height: 68, borderRadius: "50%", flexShrink: 0, border: `2px solid ${T.teal}`,
                color: T.teal, display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 500,
                fontSize: 13, transform: "rotate(-8deg)", position: "relative",
              }}
            >
              <div style={{ position: "absolute", inset: 5, borderRadius: "50%", border: `1px solid ${T.teal}`, opacity: 0.5 }} />
              접수
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 12.5, color: T.sub, marginBottom: 2 }}>접수번호</div>
              <div className="mono" style={{ fontSize: 13, fontWeight: 500, color: T.ink, marginBottom: 14, wordBreak: "break-all" }}>
                {result.id}
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 10, fontSize: 14 }}>
                <Row
                  label="문의 유형 후보"
                  value={result.inquiry_types && result.inquiry_types.length ? result.inquiry_types.join(", ") : result.inquiry_type}
                />
                <Row label="담당 부서" value={result.department} />
              </div>
              <button style={{ ...secondaryBtn, marginTop: 16, padding: "8px 14px", fontSize: 13 }} onClick={handleWriteNew}>
                새 문의 작성하기
              </button>
            </div>
          </div>
        )}

        <div style={{ background: T.navy900, borderRadius: 14, padding: 22, color: "#D7DCE5" }}>
          <div style={{ fontSize: 15, fontWeight: 500, color: "#fff", marginBottom: 10 }}>
            {phase === "result" ? "다음 단계 안내" : "등록 후 처리 흐름"}
          </div>
          {phase !== "result" ? (
            <p style={{ fontSize: 13.5, lineHeight: 1.8, margin: 0 }}>
              문의를 등록하면 먼저 <b style={{ color: "#7ED9BE" }}>민원·문의가 맞는지 확인</b>하고, 적절한 문의로
              확인되면 <b style={{ color: "#7ED9BE" }}>문의 유형 자동 확인</b>이 이뤄져 담당 부서가
              정해집니다. 이후 담당자가 답변을 준비하며, 완료되면{" "}
              <b style={{ color: "#7ED9BE" }}>답변 확인</b> 탭에 표시됩니다.
            </p>
          ) : (
            <p style={{ fontSize: 13.5, lineHeight: 1.8, margin: 0 }}>
              접수번호는 <b style={{ color: "#7ED9BE" }}>{result.id}</b>입니다.{" "}
              <b style={{ color: "#7ED9BE" }}>처리 상태 조회</b> 탭에서 진행 상황을, 완료되면{" "}
              <b style={{ color: "#7ED9BE" }}>답변 확인</b> 탭에서 답변을 볼 수 있습니다.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

/* ---------------- 탭 2. 문의 유형 자동 확인 ---------------- */
function ClassifyTab({ items }) {
  return (
    <div>
      <PageHead
        title="문의 유형 자동 확인"
        desc="접수하신 문의가 어떤 유형·담당 부서로 자동 분류됐는지 확인할 수 있습니다."
      />
      {items.length === 0 ? (
        <EmptyState text="아직 접수하신 문의가 없습니다." />
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {items.map((item) => (
            <div key={item.id} style={card}>
              <div style={{ fontSize: 12, color: T.muted, marginBottom: 8 }}>{formatTime(item.submitted_at)}</div>
              <div style={{ fontSize: 14, color: T.ink, marginBottom: 14 }}>{truncate(item.raw_text, 120)}</div>
              {item.inquiry_type ? (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  <Row label="문의 유형 후보" value={item.inquiry_types.join(", ")} />
                  <Row label="담당 부서" value={item.department} />
                  {item.candidate_departments.length > 1 && (
                    <Row label="담당부서 후보" value={item.candidate_departments.join(", ")} />
                  )}
                </div>
              ) : (
                <div style={{ color: T.muted, fontSize: 13 }}>분류 대기 중입니다.</div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/* ---------------- 탭 3. 처리 상태 조회 ---------------- */
function StatusTab({ items }) {
  return (
    <div>
      <PageHead title="처리 상태 조회" desc="접수하신 문의의 처리 진행 상황을 확인하세요." />
      {items.length === 0 ? (
        <EmptyState text="아직 접수하신 문의가 없습니다." />
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {items.map((item) => (
            <div key={item.id} style={{ ...card, padding: 16, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 12, color: T.muted, marginBottom: 3 }}>{formatTime(item.submitted_at)}</div>
                <div style={{ fontSize: 15, fontWeight: 500, color: T.ink }}>{truncate(item.raw_text, 80)}</div>
                {item.department && (
                  <div style={{ fontSize: 12.5, color: T.sub, marginTop: 3 }}>
                    {item.inquiry_type} · {item.department}
                  </div>
                )}
              </div>
              <StatusPill status={item.status} />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/* ---------------- 탭 4. 답변 확인 ---------------- */
function AnswerTab({ items }) {
  const done = items.filter((item) => item.status === "답변완료")
  const [openId, setOpenId] = useState(null)

  return (
    <div>
      <PageHead title="답변 확인" desc="답변이 완료된 문의의 확정 답변을 확인할 수 있습니다." />
      {done.length === 0 ? (
        <EmptyState text="아직 답변이 완료된 문의가 없습니다. 접수 후 잠시 기다려 주세요." />
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {done.map((item) => {
            const isOpen = openId === item.id
            return (
              <div key={item.id} style={{ ...card, padding: 0, overflow: "hidden" }}>
                <button
                  onClick={() => setOpenId(isOpen ? null : item.id)}
                  style={{ width: "100%", background: "none", border: "none", padding: "16px 18px", display: "flex", alignItems: "center", justifyContent: "space-between", cursor: "pointer", textAlign: "left", gap: 12, flexWrap: "wrap" }}
                >
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontSize: 12, color: T.muted, marginBottom: 3 }}>
                      {formatTime(item.submitted_at)} · {item.department}
                    </div>
                    <div style={{ fontSize: 15, fontWeight: 500, color: T.ink }}>{truncate(item.raw_text, 80)}</div>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <StatusPill status={item.status} />
                    {isOpen ? <ChevronUp size={16} color={T.sub} /> : <ChevronDown size={16} color={T.sub} />}
                  </div>
                </button>
                {isOpen && (
                  <div style={{ padding: "0 18px 18px", borderTop: `1px solid ${T.border}` }}>
                    <p style={{ fontSize: 14.5, lineHeight: 1.75, color: T.ink, marginTop: 14, whiteSpace: "pre-wrap" }}>
                      {item.final_answer}
                    </p>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

/* ---------------- 탭 5. 내 문의 내역 ---------------- */
// 검토중인 문의만 목록에 보여준다. 답변완료 건은 여기서 내용을 보여주는 대신,
// "답변 확인" 탭으로 안내하는 박스 하나만 띄운다 — 완료된 문의를 두 곳(내 문의
// 내역/답변 확인)에서 중복으로 보여주지 않기 위함.
function HistoryTab({ items }) {
  const reviewing = items.filter((item) => item.status === "검토중")
  const answeredCount = items.filter((item) => item.status === "답변완료").length

  return (
    <div>
      <PageHead title="내 문의 내역" desc="현재 검토 중인 문의만 모아 보여드립니다." />
      {answeredCount > 0 && (
        <div
          style={{
            display: "flex", alignItems: "center", gap: 8, marginBottom: 14, padding: "12px 14px",
            background: T.tealSoft, color: T.tealText, borderRadius: 9, fontSize: 13, fontWeight: 500,
          }}
        >
          <CheckCircle2 size={15} style={{ flexShrink: 0 }} />
          답변이 완료된 문의 {answeredCount}건이 있습니다. "답변 확인" 탭에서 내용을 확인해 주세요.
        </div>
      )}
      {reviewing.length === 0 ? (
        <EmptyState text="검토 중인 문의가 없습니다." />
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {reviewing.map((item) => (
            <div key={item.id} style={{ ...card, padding: 16 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 10, marginBottom: 6, flexWrap: "wrap" }}>
                <div style={{ fontSize: 12, color: T.muted }}>
                  {formatTime(item.submitted_at)} · {item.contact}
                </div>
                <StatusPill status={item.status} />
              </div>
              <div style={{ fontSize: 14, color: T.ink, lineHeight: 1.6, whiteSpace: "pre-wrap" }}>{item.raw_text}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/* ---------------- 메인 앱 셸 ---------------- */
const TABS = [
  { id: "register", label: "문의 등록", icon: FileText },
  { id: "classify", label: "문의 유형 자동 확인", icon: Sparkles },
  { id: "status", label: "처리 상태 조회", icon: Clock },
  { id: "answer", label: "답변 확인", icon: CheckCircle2 },
  { id: "history", label: "내 문의 내역", icon: Inbox },
]

export default function PublicSubmitView() {
  const [visitorName, setVisitorName] = useState(() => localStorage.getItem(VISITOR_NAME_KEY) || "")
  const [tab, setTab] = useState("register")
  const [items, setItems] = useState(null)
  const [itemsError, setItemsError] = useState(null)
  // "답변 확인" 탭에 아직 안 본 답변완료 건이 있으면 사이드바에 배지를 띄우기 위한
  // 목록. localStorage에 남겨서 새로고침해도(탭을 다시 안 열어봤다면) 유지된다.
  const [seenAnswerIds, setSeenAnswerIds] = useState(() =>
    visitorName ? loadSeenAnswerIds(visitorName) : new Set()
  )

  const loadItems = (name) => {
    setItemsError(null)
    fetch(`${SUBMIT_URL}?name=${encodeURIComponent(name)}`)
      .then((response) => {
        if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
        return response.json()
      })
      .then(setItems)
      .catch((err) => setItemsError(err.message))
  }

  useEffect(() => {
    if (!visitorName) return
    setSeenAnswerIds(loadSeenAnswerIds(visitorName))
    loadItems(visitorName)
    // 페이지를 켜둔 채로 있어도 담당자가 방금 답변을 완료하면 배지가 뜨도록 주기적으로
    // 조용히 새로고침한다.
    const timer = setInterval(() => loadItems(visitorName), POLL_INTERVAL_MS)
    return () => clearInterval(timer)
  }, [visitorName])

  const unseenAnsweredCount = (items || []).filter(
    (item) => item.status === "답변완료" && !seenAnswerIds.has(item.id)
  ).length

  // "답변 확인" 탭을 열면 그 시점에 답변완료인 건들을 전부 "확인함"으로 표시해
  // 배지가 사라지게 한다.
  const handleSelectTab = (id) => {
    setTab(id)
    if (id === "answer" && items) {
      const nextSeen = new Set(seenAnswerIds)
      items.forEach((item) => {
        if (item.status === "답변완료") nextSeen.add(item.id)
      })
      setSeenAnswerIds(nextSeen)
      saveSeenAnswerIds(visitorName, nextSeen)
    }
  }

  if (!visitorName) {
    return (
      <NameGate
        onConfirm={(name) => {
          localStorage.setItem(VISITOR_NAME_KEY, name)
          setVisitorName(name)
        }}
      />
    )
  }

  const handleSwitchName = () => {
    localStorage.removeItem(VISITOR_NAME_KEY)
    setVisitorName("")
    setTab("register")
    setItems(null)
  }

  return (
    <div style={{ fontFamily: "'Pretendard','Apple SD Gothic Neo','Malgun Gothic',sans-serif", minHeight: "100vh" }}>
      <style>{`
        .cf-nav-item:hover { background: #1B2A44 !important; }
        input:focus-visible, textarea:focus-visible, button:focus-visible {
          outline: 2px solid ${T.teal}; outline-offset: 2px;
        }
        @keyframes cf-spin { to { transform: rotate(360deg); } }
        @keyframes cf-bounce {
          0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
          40% { transform: scale(1); opacity: 1; }
        }
        @media (prefers-reduced-motion: reduce) {
          *[style*="cf-spin"], *[style*="cf-bounce"] { animation: none !important; }
        }
        @media (max-width: 760px) {
          .cf-shell { flex-direction: column !important; }
          .cf-sidebar { width: 100% !important; flex-direction: row !important; align-items: center !important; padding: 14px 16px !important; overflow-x: auto; }
          .cf-sidebar-nav { flex-direction: row !important; gap: 6px !important; margin-top: 0 !important; }
          .cf-sidebar-foot { display: none !important; }
          .cf-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
      <div className="cf-shell" style={{ display: "flex", minHeight: "100vh", background: T.page }}>
        <aside
          className="cf-sidebar"
          style={{ width: 250, flexShrink: 0, background: T.navy900, color: "#D7DCE5", padding: "24px 18px", display: "flex", flexDirection: "column" }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 26 }}>
            <div style={{ width: 38, height: 38, borderRadius: 9, background: T.teal, color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 500, fontSize: 14, flexShrink: 0 }}>
              CF
            </div>
            <div>
              <div style={{ fontSize: 15, fontWeight: 500, color: "#fff" }}>CivicFlow 민원포털</div>
              <div style={{ fontSize: 11.5, color: "#7C8698" }}>{visitorName}님</div>
            </div>
          </div>

          <nav className="cf-sidebar-nav" style={{ display: "flex", flexDirection: "column", gap: 3 }}>
            {TABS.map((t, idx) => {
              const Icon = t.icon
              const active = tab === t.id
              const showBadge = t.id === "answer" && unseenAnsweredCount > 0
              return (
                <button
                  key={t.id}
                  className="cf-nav-item"
                  onClick={() => handleSelectTab(t.id)}
                  style={{
                    display: "flex", alignItems: "center", gap: 10,
                    background: active ? T.navy700 : "transparent", border: "none",
                    borderLeft: active ? `2px solid ${T.teal}` : "2px solid transparent",
                    color: active ? "#fff" : "#AEB7C4", padding: "10px 10px", borderRadius: 6,
                    fontSize: 13.5, fontWeight: active ? 500 : 400, cursor: "pointer", textAlign: "left", whiteSpace: "nowrap",
                  }}
                >
                  <Icon size={16} />
                  <span style={{ flex: 1 }}>{t.label}</span>
                  {showBadge ? (
                    <span
                      style={{
                        background: "#E24C4C", color: "#fff", fontSize: 10.5, fontWeight: 700,
                        borderRadius: 999, minWidth: 17, height: 17, display: "inline-flex",
                        alignItems: "center", justifyContent: "center", padding: "0 5px",
                      }}
                    >
                      {unseenAnsweredCount}
                    </span>
                  ) : (
                    <span style={{ fontSize: 11, color: active ? T.teal : "#5B6472" }}>{String(idx + 1).padStart(2, "0")}</span>
                  )}
                </button>
              )
            })}
          </nav>

          <div className="cf-sidebar-foot" style={{ marginTop: "auto", paddingTop: 22, borderTop: "1px solid #22314A" }}>
            <button
              onClick={handleSwitchName}
              style={{ background: "none", border: "none", color: T.teal, fontSize: 11.5, fontWeight: 600, cursor: "pointer", padding: 0, marginBottom: 12 }}
            >
              {visitorName}님이 아닌가요?
            </button>
            <div style={{ fontSize: 11, color: "#5B6472", lineHeight: 1.7 }}>
              LangGraph StateGraph 기반
              <br />
              자동 분류 · RAG · 규칙엔진
            </div>
          </div>
        </aside>

        <main style={{ flex: 1, padding: "28px 32px 60px", minWidth: 0 }}>
          <div style={{ maxWidth: 900, margin: "0 auto" }}>
            {itemsError && (
              <div style={{ color: T.danger, fontSize: 13, display: "flex", gap: 6, alignItems: "center", marginBottom: 16 }}>
                <AlertTriangle size={14} /> 내역을 불러오지 못했습니다: {itemsError}
              </div>
            )}
            {tab === "register" && (
              <RegisterTab visitorName={visitorName} onSubmitted={() => loadItems(visitorName)} />
            )}
            {tab === "classify" && <ClassifyTab items={items || []} />}
            {tab === "status" && <StatusTab items={items || []} />}
            {tab === "answer" && <AnswerTab items={items || []} />}
            {tab === "history" && <HistoryTab items={items || []} />}
          </div>
        </main>
      </div>
    </div>
  )
}
