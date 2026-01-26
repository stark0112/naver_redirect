from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_db
from app.routers import search, products, ranking
from app.services.cleanup import cleanup_old_rankings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 실행"""
    # 시작 시: DB 초기화 + 오래된 데이터 정리
    await init_db()
    await cleanup_old_rankings(days=7)  # 7일 지난 기록 삭제
    yield
    # 종료 시: 정리 작업


app = FastAPI(
    title="네이버 쇼핑 크롤러",
    description="콜영업팀을 위한 네이버 쇼핑 데이터 크롤링 서비스",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 파일 & 템플릿
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 라우터 등록
app.include_router(search.router)
app.include_router(products.router)
app.include_router(ranking.router)


@app.get("/")
async def index(request: Request):
    """메인 대시보드 페이지"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health_check():
    """헬스 체크"""
    return {"status": "ok"}


@app.post("/api/cleanup")
async def manual_cleanup(days: int = 30):
    """오래된 순위 기록 수동 정리"""
    deleted = await cleanup_old_rankings(days=days)
    return {"deleted": deleted, "message": f"{days}일 이전 기록 {deleted}개 삭제됨"}
