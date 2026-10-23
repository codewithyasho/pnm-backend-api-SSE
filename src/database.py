from pathlib import Path
from sqlmodel import SQLModel, create_engine, Session

DB_PATH = Path(__file__).resolve().parent.parent / "database.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, echo=True)


def init_db():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
