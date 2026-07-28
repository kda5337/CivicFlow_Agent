-- 22학번(cohort 2022) AI·소프트웨어학부 인공지능전공 교육과정 및 졸업요건 시드 데이터.
-- schema.sql의 graduation_requirements / curriculum_courses 테이블을 채운다.

-- 1) 졸업 이수학점 기준
INSERT INTO graduation_requirements (cohort, category, required_credits) VALUES
    (2022, '기초교양', 17),
    (2022, '융합교양', 7),
    (2022, '계열교양', NULL),
    (2022, '전공필수', 38),
    (2022, '전공선택', 34),
    (2022, '총졸업학점', 120);

-- 2) 공통과정 (1~2학년, track = NULL)

-- 1학년 1학기
INSERT INTO curriculum_courses (requirement_id, track, year, semester, course_name, credits, theory_hours, practice_hours)
SELECT id, NULL, 1, 1, v.course_name, v.credits, v.theory_hours, v.practice_hours
FROM graduation_requirements, (VALUES
    ('기초교양', 'College English 1', 1, 0, 2),
    ('기초교양', '인성세미나', 1, 0, 1),
    ('기초교양', '창의 NTree', 1, 0, 2),
    ('기초교양', '인성과 리더십', 2, 2, 0),
    ('기초교양', '창의와 사고', 2, 2, 0),
    ('기초교양', '지능형 정보기술', 2, 2, 0),
    ('전공필수', '프로그래밍기초', 3, 2, 1),
    ('전공필수', '웹프로그래밍', 3, 2, 1),
    ('전공필수', '소프트웨어수학', 3, 3, 0)
) AS v(category, course_name, credits, theory_hours, practice_hours)
WHERE graduation_requirements.cohort = 2022 AND graduation_requirements.category = v.category;

-- 1학년 2학기
INSERT INTO curriculum_courses (requirement_id, track, year, semester, course_name, credits, theory_hours, practice_hours)
SELECT id, NULL, 1, 2, v.course_name, v.credits, v.theory_hours, v.practice_hours
FROM graduation_requirements, (VALUES
    ('기초교양', 'College English 2', 1, 0, 2),
    ('기초교양', '창의와 사고', 2, 2, 0),
    ('기초교양', '응용 프로그래밍', 2, 1, 1),
    ('기초교양', '과학기술글쓰기', 2, 2, 0),
    ('융합교양', '융합교양', 3, 3, 0),
    ('전공필수', '기업과 리더십', 2, 2, 0),
    ('전공필수', '문제해결기법', 3, 2, 1),
    ('전공필수', '로봇공학', 3, 1, 2),
    ('전공선택', '오픈소스SW', 1, 1, 0)
) AS v(category, course_name, credits, theory_hours, practice_hours)
WHERE graduation_requirements.cohort = 2022 AND graduation_requirements.category = v.category;

-- 2학년 1학기
INSERT INTO curriculum_courses (requirement_id, track, year, semester, course_name, credits, theory_hours, practice_hours)
SELECT id, NULL, 2, 1, v.course_name, v.credits, v.theory_hours, v.practice_hours
FROM graduation_requirements, (VALUES
    ('융합교양', '융합교양', 2, 2, 0),
    ('전공필수', '자료구조 및 실습', 3, 2, 1),
    ('전공필수', '객체지향프로그래밍', 3, 2, 1),
    ('전공필수', '운영체제', 3, 2, 1),
    ('전공필수', '확률통계', 3, 3, 0)
) AS v(category, course_name, credits, theory_hours, practice_hours)
WHERE graduation_requirements.cohort = 2022 AND graduation_requirements.category = v.category;

-- 2학년 2학기
INSERT INTO curriculum_courses (requirement_id, track, year, semester, course_name, credits, theory_hours, practice_hours)
SELECT id, NULL, 2, 2, v.course_name, v.credits, v.theory_hours, v.practice_hours
FROM graduation_requirements, (VALUES
    ('기초교양', '사회봉사', 0, 0, 0),
    ('융합교양', '융합교양', 2, 2, 0),
    ('전공선택', '컴퓨터네트워크 및 실습', 3, 2, 1),
    ('전공선택', '알고리즘', 3, 2, 1),
    ('전공선택', '데이터베이스 및 실습', 3, 2, 1),
    ('전공필수', '경영학의 이해', 3, 3, 0)
) AS v(category, course_name, credits, theory_hours, practice_hours)
WHERE graduation_requirements.cohort = 2022 AND graduation_requirements.category = v.category;

-- 3학년 1학기 (공통, 트랙 분리 전)
INSERT INTO curriculum_courses (requirement_id, track, year, semester, course_name, credits, theory_hours, practice_hours)
SELECT id, NULL, 3, 1, v.course_name, v.credits, v.theory_hours, v.practice_hours
FROM graduation_requirements, (VALUES
    ('전공선택', 'AI수학', 3, 3, 0),
    ('전공선택', '모바일프로그래밍', 3, 2, 1),
    ('전공선택', '디지털마케팅', 3, 3, 0)
) AS v(category, course_name, credits, theory_hours, practice_hours)
WHERE graduation_requirements.cohort = 2022 AND graduation_requirements.category = v.category;

-- 3학년 2학기
INSERT INTO curriculum_courses (requirement_id, track, year, semester, course_name, credits, theory_hours, practice_hours)
SELECT id, NULL, 3, 2, v.course_name, v.credits, v.theory_hours, v.practice_hours
FROM graduation_requirements, (VALUES
    ('기초교양', '취·창업 진로세미나', 1, 1, 0),
    ('전공필수', 'P-실무프로젝트 (졸업작품 I)', 3, 7, 8),
    ('전공선택', '컴퓨터구조', 3, 4, 0)
) AS v(category, course_name, credits, theory_hours, practice_hours)
WHERE graduation_requirements.cohort = 2022 AND graduation_requirements.category = v.category;

-- 4학년 1학기
INSERT INTO curriculum_courses (requirement_id, track, year, semester, course_name, credits, theory_hours, practice_hours)
SELECT id, NULL, 4, 1, v.course_name, v.credits, v.theory_hours, v.practice_hours
FROM graduation_requirements, (VALUES
    ('전공필수', '졸업작품 Ⅱ (캡스톤디자인)', 3, 0, 3),
    ('전공선택', '현장실습', 1, 0, 2),
    ('전공선택', 'AI신기술특론', 3, 2, 1)
) AS v(category, course_name, credits, theory_hours, practice_hours)
WHERE graduation_requirements.cohort = 2022 AND graduation_requirements.category = v.category;

-- 4학년 2학기
INSERT INTO curriculum_courses (requirement_id, track, year, semester, course_name, credits, theory_hours, practice_hours)
SELECT id, NULL, 4, 2, v.course_name, v.credits, v.theory_hours, v.practice_hours
FROM graduation_requirements, (VALUES
    ('전공선택', '학생자율연구', 3, 1, 2),
    ('전공선택', '테크기업경영', 3, 2, 1)
) AS v(category, course_name, credits, theory_hours, practice_hours)
WHERE graduation_requirements.cohort = 2022 AND graduation_requirements.category = v.category;

-- 3) 트랙과정 (3~4학년, 전공선택). Language-AI/Vision-AI 공통 과목은 트랙별로 행을 중복 저장한다.

INSERT INTO curriculum_courses (requirement_id, track, year, semester, course_name, credits, theory_hours, practice_hours)
SELECT id, v.track, v.year, v.semester, v.course_name, v.credits, v.theory_hours, v.practice_hours
FROM graduation_requirements, (VALUES
    ('Language-AI', 3, 1, '인공지능개론', 3, 2, 1),
    ('Language-AI', 3, 1, '데이터과학', 3, 2, 1),
    ('Language-AI', 3, 2, '머신러닝', 3, 2, 2),
    ('Language-AI', 3, 2, '자연어처리개론', 3, 2, 2),
    ('Language-AI', 4, 1, '딥러닝', 3, 2, 1),
    ('Language-AI', 4, 1, '음성언어처리', 3, 2, 1),
    ('Language-AI', 4, 2, 'AI프로젝트', 3, 1, 2),
    ('Vision-AI', 3, 1, '인공지능개론', 3, 2, 1),
    ('Vision-AI', 3, 1, '데이터과학', 3, 2, 1),
    ('Vision-AI', 3, 2, '머신러닝', 3, 2, 2),
    ('Vision-AI', 3, 2, '기초 컴퓨터비전', 3, 2, 2),
    ('Vision-AI', 4, 1, '딥러닝', 3, 2, 1),
    ('Vision-AI', 4, 1, '영상처리', 3, 2, 1),
    ('Vision-AI', 4, 2, 'AI프로젝트', 3, 1, 2)
) AS v(track, year, semester, course_name, credits, theory_hours, practice_hours)
WHERE graduation_requirements.cohort = 2022 AND graduation_requirements.category = '전공선택';
