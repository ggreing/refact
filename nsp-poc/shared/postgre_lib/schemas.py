from pydantic import BaseModel
from typing import Optional
import datetime

class CourseBase(BaseModel):
    course_id: str
    course_name: Optional[str] = None
    course_description: Optional[str] = None
    product_family: Optional[str] = None
    category: Optional[str] = None
    difficulty: Optional[str] = None
    keywords: Optional[str] = None
    estimated_time_minutes: Optional[int] = None
    prerequisite_courses: Optional[str] = None
    related_courses: Optional[str] = None
    created_date: Optional[datetime.date] = None
    link: Optional[str] = None

class CourseCreate(CourseBase):
    pass

class Course(CourseBase):
    class Config:
        orm_mode = True
