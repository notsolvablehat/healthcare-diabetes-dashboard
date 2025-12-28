from sqlalchemy import Boolean, Column, String

from src.database.core import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_pass = Column(String)
    is_patient = Column(Boolean, default=True)
    is_doctor = Column(Boolean, default=False)
    has_diabetes = Column(Boolean, default=True)

    def __repr__(self) -> str:
        return f"<User(email={self.email}), username={self.username}, diabetic={self.has_diabetes}, is_patient={self.is_patient}, is_doctor={self.is_doctor}>"
