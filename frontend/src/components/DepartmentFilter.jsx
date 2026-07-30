import { useEffect, useState } from 'react'

const DEPARTMENTS_URL = 'http://localhost:8000/departments'

export const ALL_DEPARTMENTS = '전체'

// 문의 접수함/답변 완료함에서 부서별로 걸러볼 수 있게 하는 칩 목록. rules.yaml에
// 있는 담당부서 전체를 AnalysisView의 담당부서 선택과 같은 소스(GET /departments)로
// 가져와서, 부서명이 한곳(rules.yaml)에서만 관리되게 한다.
export default function DepartmentFilter({ value, onChange }) {
  const [departments, setDepartments] = useState([])

  useEffect(() => {
    fetch(DEPARTMENTS_URL)
      .then((response) => response.json())
      .then(setDepartments)
      .catch(() => setDepartments([]))
  }, [])

  return (
    <div className="dept-picker" style={{ marginBottom: 14 }}>
      {[ALL_DEPARTMENTS, ...departments].map((dept) => (
        <button
          key={dept}
          type="button"
          className={`dept-chip${dept === value ? ' active' : ''}`}
          onClick={() => onChange(dept)}
        >
          {dept}
        </button>
      ))}
    </div>
  )
}
