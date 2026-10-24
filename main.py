from routes.users import router as user_router
from routes.chat import chat_router
from src.database import init_db

from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware

from fastapi import FastAPI
import uvicorn



@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    print("\nDatabase tables created [OK].")
    yield
    print("\nshutting down the app")


app = FastAPI(
    title="People Network Management LLP ADMIN DASHBOARD",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user_router)
app.include_router(chat_router)


@app.get("/")
def home():
    return {
        "status": "healthy",
        "message": "visit /docs"
    }



if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
