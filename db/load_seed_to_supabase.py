"""schema.sql의 graduation_requirements/curriculum_courses 테이블을 Supabase(Postgres)에 생성하고,
seed_curriculum_2022.sql의 22학번 데이터를 적재한다. 이미 있으면 건너뛴다(재실행해도 안전).

사전 준비: .env의 SUPABASE_DATABASE_URL (Supabase 프로젝트 Settings > Database > Connection string).

실행:
    cd db
    python load_seed_to_supabase.py
"""
import os
import re
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_DIR = Path(__file__).resolve().parent
TARGET_TABLES = ("graduation_requirements", "curriculum_courses")


def extract_create_table_statements(schema_sql: str, table_names) -> list[str]:
    statements = re.split(r";\s*\n", schema_sql)
    return [
        stmt.strip() + ";"
        for stmt in statements
        if any(f"CREATE TABLE {name}" in stmt for name in table_names)
    ]


def table_exists(cur, table_name: str) -> bool:
    cur.execute(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = %s)",
        (table_name,),
    )
    return cur.fetchone()[0]


def main():
    database_url = os.getenv("SUPABASE_DATABASE_URL")
    if not database_url:
        raise SystemExit("SUPABASE_DATABASE_URL이 .env에 설정되어 있지 않습니다.")

    schema_sql = (DB_DIR / "schema.sql").read_text(encoding="utf-8")
    seed_sql = (DB_DIR / "seed_curriculum_2022.sql").read_text(encoding="utf-8")

    conn = psycopg2.connect(database_url)
    try:
        with conn:
            with conn.cursor() as cur:
                for statement in extract_create_table_statements(schema_sql, TARGET_TABLES):
                    table_name = statement.split("CREATE TABLE")[1].split("(")[0].strip()
                    if table_exists(cur, table_name):
                        print(f"'{table_name}' 테이블이 이미 존재해 생성을 건너뜁니다.")
                        continue
                    cur.execute(statement)
                    print(f"'{table_name}' 테이블 생성 완료.")

            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM graduation_requirements WHERE cohort = 2022")
                (existing,) = cur.fetchone()
                if existing > 0:
                    print("cohort=2022 데이터가 이미 있어 시드 삽입을 건너뜁니다.")
                else:
                    cur.execute(seed_sql)
                    print("22학번 시드 데이터 삽입 완료.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
