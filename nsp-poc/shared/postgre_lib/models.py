from sqlalchemy import Column, Integer, String, Date, Text
from .database import Base

class Course(Base):
    __tablename__ = "courses"

    course_id = Column(String, primary_key=True, index=True)
    course_name = Column(Text)
    course_description = Column(Text)
    product_family = Column(Text)
    category = Column(Text)
    difficulty = Column(Text)
    keywords = Column(Text)
    estimated_time_minutes = Column(Integer)
    prerequisite_courses = Column(Text)
    related_courses = Column(Text)
    created_date = Column(Date)
    link = Column(Text)
