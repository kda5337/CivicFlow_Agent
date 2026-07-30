// 문의 접수 상태(citizen_submissions.status)를 배지 색상 클래스로 매핑.
export function statusBadgeClass(status) {
  if (status === '답변완료') return 'low'
  if (status === '검토중') return 'mid'
  return 'done'
}
