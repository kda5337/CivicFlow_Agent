// 우선순위 문자열(rules.yaml이 정하는 낮음/보통/높음/최상)을 배지 색상 클래스로 매핑.
export function priorityBadgeClass(우선순위) {
  if (우선순위 === '최상' || 우선순위 === '높음') return 'high'
  if (우선순위 === '보통') return 'mid'
  return 'low'
}

// 문의 접수함 정렬용 숫자 랭크 (높을수록 먼저 보여줌). rules.yaml/rules.py의
// _PRIORITY_RANK와 같은 순서다.
export function priorityRank(우선순위) {
  if (우선순위 === '최상') return 3
  if (우선순위 === '높음') return 2
  if (우선순위 === '보통') return 1
  return 0
}
