// 우선순위 문자열(rules.yaml이 정하는 낮음/보통/높음/최상)을 배지 색상 클래스로 매핑.
export function priorityBadgeClass(우선순위) {
  if (우선순위 === '최상' || 우선순위 === '높음') return 'high'
  if (우선순위 === '보통') return 'mid'
  return 'low'
}
