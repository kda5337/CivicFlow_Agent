// 접수 시각과 무관하게, 접수일 "다음날" 오전 9시가 처리 마감이다 — 예: 7/28 어느
// 시각에 접수했든 7/29 09:00까지 미처리면 지연. 지금이 그 마감을 지났는지로 판정한다.
const DELAY_CUTOFF_HOUR = 9

export function delayDeadline(submittedAt) {
  const submitted = new Date(submittedAt)
  return new Date(submitted.getFullYear(), submitted.getMonth(), submitted.getDate() + 1, DELAY_CUTOFF_HOUR, 0, 0, 0)
}

export function isDelayed(submittedAt) {
  return Date.now() > delayDeadline(submittedAt).getTime()
}
