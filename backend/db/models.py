from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from .database import Base

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    upload_date = Column(DateTime, default=datetime.utcnow)
    chunks_count = Column(Integer, default=0)
    status = Column(String, default="processing") # "processing", "processed", "error"
