from datetime import datetime

from sqlalchemy import JSON,Boolean,DateTime,Float,ForeignKey,Integer,String,Text
from sqlalchemy.orm import Mapped,mapped_column,relationship

from src.database.database import Base


class User(Base):
    __tablename__="users"

    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    name:Mapped[str]=mapped_column(String(100))
    email:Mapped[str]=mapped_column(String(255),unique=True,index=True)
    password_hash:Mapped[str]=mapped_column(String(255))
    role:Mapped[str]=mapped_column(String(20),default="user")
    is_active:Mapped[bool]=mapped_column(Boolean,default=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

    analyses:Mapped[list["Analysis"]]=relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class Analysis(Base):
    __tablename__="analyses"

    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    user_id:Mapped[int]=mapped_column(
        ForeignKey("users.id",ondelete="CASCADE"),
        index=True,
    )
    run_id:Mapped[str]=mapped_column(String(100),unique=True,index=True)
    filename:Mapped[str]=mapped_column(String(255))
    input_type:Mapped[str]=mapped_column(String(20))
    layer_type:Mapped[str|None]=mapped_column(String(100),nullable=True)
    status:Mapped[str]=mapped_column(String(50))
    total_findings:Mapped[int]=mapped_column(Integer,default=0)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

    user:Mapped["User"]=relationship(back_populates="analyses")

    findings:Mapped[list["Finding"]]=relationship(
        back_populates="analysis",
        cascade="all, delete-orphan",
    )

    report:Mapped["Report|None"]=relationship(
        back_populates="analysis",
        cascade="all, delete-orphan",
        uselist=False,
    )


class Finding(Base):
    __tablename__="findings"

    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    analysis_id:Mapped[int]=mapped_column(
        ForeignKey("analyses.id",ondelete="CASCADE"),
        index=True,
    )
    finding_id:Mapped[str|None]=mapped_column(String(100),nullable=True)
    rule_id:Mapped[str|None]=mapped_column(String(100),nullable=True)
    feature_id:Mapped[str|None]=mapped_column(String(255),nullable=True)
    error_type:Mapped[str]=mapped_column(String(100))
    severity:Mapped[str|None]=mapped_column(String(50),nullable=True)
    status:Mapped[str|None]=mapped_column(String(50),nullable=True)
    message:Mapped[str|None]=mapped_column(Text,nullable=True)
    recommendation:Mapped[str|None]=mapped_column(Text,nullable=True)
    confidence:Mapped[float|None]=mapped_column(Float,nullable=True)
    location:Mapped[dict|list|None]=mapped_column(JSON,nullable=True)
    measurements:Mapped[list|dict|None]=mapped_column(JSON,nullable=True)

    analysis:Mapped["Analysis"]=relationship(back_populates="findings")


class Report(Base):
    __tablename__="reports"

    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    analysis_id:Mapped[int]=mapped_column(
        ForeignKey("analyses.id",ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    report_path:Mapped[str|None]=mapped_column(String(500),nullable=True)
    audio_path:Mapped[str|None]=mapped_column(String(500),nullable=True)
    audio_text:Mapped[str|None]=mapped_column(Text,nullable=True)
    report_json:Mapped[dict|None]=mapped_column(JSON,nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

    analysis:Mapped["Analysis"]=relationship(back_populates="report")