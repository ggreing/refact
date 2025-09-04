from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from shared.postgre_lib import crud, schemas, models
from shared.postgre_lib.database import get_db, engine

models.Base.metadata.create_all(bind=engine)

router = APIRouter()

@router.post("/postgre/", response_model=schemas.Course)
def create_postgre(course: schemas.CourseCreate, db: Session = Depends(get_db)):
    db_course = crud.get_course(db, course_id=course.course_id)
    if db_course:
        raise HTTPException(status_code=400, detail="Course already registered")
    return crud.create_course(db=db, course=course)

@router.get("/postgre/", response_model=List[schemas.Course])
def read_courses(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    courses = crud.get_courses(db, skip=skip, limit=limit)
    return courses

@router.get("/postgre/{course_id}", response_model=schemas.Course)
def read_course(course_id: str, db: Session = Depends(get_db)):
    db_course = crud.get_course(db, course_id=course_id)
    if db_course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return db_course

@router.post("/postgre/filter", response_model=List[schemas.Course])
def read_courses_with_filter(course_filter: schemas.Course, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    courses = crud.get_courses_with_filter(db, course_filter=course_filter, skip=skip, limit=limit)
    return courses

@router.delete("/postgre/{course_id}", response_model=schemas.Course)
def delete_course(course_id: str, db: Session = Depends(get_db)):
    db_course = crud.delete_course(db, course_id=course_id)
    if db_course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return db_course