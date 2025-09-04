-- courses 테이블 생성
CREATE TABLE courses (
    course_id VARCHAR(255) PRIMARY KEY,
    course_name TEXT,
    course_description TEXT,
    product_family TEXT,
    category TEXT,
    difficulty TEXT,
    keywords TEXT,
    estimated_time_minutes INTEGER,
    prerequisite_courses TEXT,
    related_courses TEXT,
    created_date DATE,
    link TEXT
);

-- CSV 파일에서 데이터 가져오기
-- COPY courses FROM '/docker-entrypoint-initdb.d/metadata_course.csv' DELIMITER ',' CSV HEADER;
COPY courses(course_id, course_name, course_description, product_family, category, difficulty, keywords, estimated_time_minutes, prerequisite_courses, related_courses, created_date, Link) FROM '/docker-entrypoint-initdb.d/metadata_course.csv' DELIMITER ',' CSV HEADER;
