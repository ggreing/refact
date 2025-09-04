FROM postgres:latest

COPY init.sql /docker-entrypoint-initdb.d/
COPY metadata_course.csv /docker-entrypoint-initdb.d/
