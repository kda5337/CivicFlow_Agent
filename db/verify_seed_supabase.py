"""Supabase(Postgres)에 적재된 22학번 커리큘럼 데이터가 올바른지 확인한다.

- graduation_requirements / curriculum_courses 행 수
- 카테고리별 졸업요건 학점 vs 실제 과목 합계 대조
- 샘플 데이터 출력

실행:
    cd db
    python verify_seed_supabase.py
"""
import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()


def main():
    database_url = os.getenv("SUPABASE_DATABASE_URL")
    if not database_url:
        raise SystemExit("SUPABASE_DATABASE_URL이 .env에 설정되어 있지 않습니다.")

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM graduation_requirements WHERE cohort = 2022")
            (req_count,) = cur.fetchone()
            print(f"graduation_requirements (cohort=2022) 행 수: {req_count} (기대값: 6)")

            cur.execute(
                """
                SELECT COUNT(*) FROM curriculum_courses cc
                JOIN graduation_requirements gr ON gr.id = cc.requirement_id
                WHERE gr.cohort = 2022
                """
            )
            (course_count,) = cur.fetchone()
            print(f"curriculum_courses (cohort=2022) 행 수: {course_count} (기대값: 54)")

            print("\n=== 카테고리별 졸업요건 vs 실제 합계 ===")
            cur.execute(
                """
                SELECT gr.category, gr.required_credits, COALESCE(SUM(cc.credits), 0) AS actual_credits
                FROM graduation_requirements gr
                LEFT JOIN curriculum_courses cc ON cc.requirement_id = gr.id
                WHERE gr.cohort = 2022
                GROUP BY gr.category, gr.required_credits
                ORDER BY gr.category
                """
            )
            for category, required, actual in cur.fetchall():
                if category == "계열교양":
                    note = "(해당 과목 없음, 정상)"
                elif category == "총졸업학점":
                    note = "(과목에 직접 매핑되지 않는 총량, 정상)"
                elif category == "전공선택":
                    note = "OK" if actual == required else "(선택과목 특성상 실제>요건 정상)"
                else:
                    note = "OK" if actual == required else "MISMATCH"
                print(f"{category}: 요건={required}, 실제합계={actual}  {note}")

            print("\n=== 샘플 데이터 5건 ===")
            cur.execute(
                """
                SELECT cc.year, cc.semester, cc.track, cc.course_name, cc.credits
                FROM curriculum_courses cc
                JOIN graduation_requirements gr ON gr.id = cc.requirement_id
                WHERE gr.cohort = 2022
                ORDER BY cc.year, cc.semester
                LIMIT 5
                """
            )
            for row in cur.fetchall():
                print(row)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
