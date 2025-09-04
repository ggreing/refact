from sqlalchemy.orm import Session
from . import models, schemas
from typing import List, Optional

def get_course(db: Session, course_id: str) -> Optional[models.Course]:
    return db.query(models.Course).filter(models.Course.course_id == course_id).first()

def get_courses(db: Session, skip: int = 0, limit: int = 100) -> List[models.Course]:
    return db.query(models.Course).offset(skip).limit(limit).all()

def get_courses_with_filter(db: Session, course_filter: schemas.Course, skip: int = 0, limit: int = 100) -> List[models.Course]:
    query = db.query(models.Course)
    if course_filter.course_name:
        query = query.filter(models.Course.course_name.contains(course_filter.course_name))
    if course_filter.category:
        query = query.filter(models.Course.category == course_filter.category)
    if course_filter.difficulty:
        query = query.filter(models.Course.difficulty == course_filter.difficulty)
    return query.offset(skip).limit(limit).all()

def create_course(db: Session, course: schemas.CourseCreate) -> models.Course:
    db_course = models.Course(**course.dict())
    db.add(db_course)
    db.commit()
    db.refresh(db_course)
    return db_course

def delete_course(db: Session, course_id: str):
    db_course = db.query(models.Course).filter(models.Course.course_id == course_id).first()
    if db_course:
        db.delete(db_course)
        db.commit()
    return db_course