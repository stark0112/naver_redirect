from datetime import date, timedelta
from typing import List, Optional
from io import BytesIO
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
from openpyxl import Workbook
from app.database import get_db
from app.models import Keyword, Product, RankingHistory
from app.schemas import KeywordResponse, ProductResponse, DashboardStats

router = APIRouter(prefix="/api", tags=["products"])


@router.get("/keywords", response_model=List[KeywordResponse])
async def get_keywords(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """키워드 목록 조회"""
    # 키워드별 상품 수 포함
    result = await db.execute(
        select(
            Keyword,
            func.count(Product.id).label("product_count")
        )
        .outerjoin(Product)
        .group_by(Keyword.id)
        .order_by(desc(Keyword.created_at))
        .offset(skip)
        .limit(limit)
    )

    keywords = []
    for row in result:
        keyword = row[0]
        keyword.product_count = row[1]
        keywords.append(KeywordResponse(
            id=keyword.id,
            keyword=keyword.keyword,
            created_at=keyword.created_at,
            product_count=row[1]
        ))

    return keywords


@router.get("/keywords/{keyword_id}/products", response_model=List[ProductResponse])
async def get_keyword_products(
    keyword_id: int,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """특정 키워드의 상품 목록 조회"""
    # 키워드 확인
    keyword = await db.get(Keyword, keyword_id)
    if not keyword:
        raise HTTPException(status_code=404, detail="키워드를 찾을 수 없습니다")

    # 상품 조회 (순위 정보 포함)
    result = await db.execute(
        select(Product)
        .where(Product.keyword_id == keyword_id)
        .options(selectinload(Product.rankings))
        .offset(skip)
        .limit(limit)
    )
    products = result.scalars().all()

    # 응답 생성 (순위 변동 계산)
    responses = []
    for product in products:
        # 최근 2개의 순위 기록으로 비교
        sorted_rankings = sorted(product.rankings, key=lambda r: r.recorded_at, reverse=True)

        current_rank = sorted_rankings[0].rank_position if len(sorted_rankings) >= 1 else None
        previous_rank = sorted_rankings[1].rank_position if len(sorted_rankings) >= 2 else None

        # 순위 변동 계산 (이전 순위 - 현재 순위, 양수면 상승)
        rank_change = None
        if current_rank and previous_rank:
            rank_change = previous_rank - current_rank

        responses.append(ProductResponse(
            id=product.id,
            keyword_id=product.keyword_id,
            product_name=product.product_name,
            product_url=product.product_url,
            naver_product_id=product.naver_product_id,
            product_image=product.product_image,
            price=product.price,
            store_name=product.store_name,
            seller_name=product.seller_name,
            phone_number=product.phone_number,
            phone_crawled=product.phone_crawled,
            created_at=product.created_at,
            current_rank=current_rank,
            rank_change=rank_change
        ))

    return responses


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """대시보드 통계"""
    today = date.today()

    # 총 키워드 수
    total_keywords = await db.scalar(select(func.count(Keyword.id)))

    # 총 상품 수
    total_products = await db.scalar(select(func.count(Product.id)))

    # 전화번호 성공/실패
    phone_success = await db.scalar(
        select(func.count(Product.id)).where(Product.phone_crawled == 1)
    )
    phone_failed = await db.scalar(
        select(func.count(Product.id)).where(Product.phone_crawled == -1)
    )

    # 오늘 크롤링한 상품 수
    today_crawled = await db.scalar(
        select(func.count(Product.id)).where(
            func.date(Product.created_at) == today
        )
    )

    return DashboardStats(
        total_keywords=total_keywords or 0,
        total_products=total_products or 0,
        phone_success=phone_success or 0,
        phone_failed=phone_failed or 0,
        today_crawled=today_crawled or 0
    )


@router.get("/keywords/{keyword_id}/export")
async def export_to_excel(
    keyword_id: int,
    db: AsyncSession = Depends(get_db)
):
    """상품 목록 엑셀 다운로드"""
    # 키워드 확인
    keyword = await db.get(Keyword, keyword_id)
    if not keyword:
        raise HTTPException(status_code=404, detail="키워드를 찾을 수 없습니다")

    # 상품 조회
    result = await db.execute(
        select(Product)
        .where(Product.keyword_id == keyword_id)
        .options(selectinload(Product.rankings))
    )
    products = result.scalars().all()

    # 엑셀 생성
    wb = Workbook()
    ws = wb.active
    ws.title = "검색결과"

    # 헤더
    headers = ["순위", "상품명", "스토어명", "판매자", "전화번호", "가격", "상품URL"]
    ws.append(headers)

    # 데이터
    for product in products:
        # 최신 순위 찾기
        sorted_rankings = sorted(product.rankings, key=lambda r: r.recorded_at, reverse=True)
        current_rank = sorted_rankings[0].rank_position if sorted_rankings else "-"

        ws.append([
            current_rank,
            product.product_name,
            product.store_name,
            product.seller_name,
            product.phone_number or "-",
            product.price,
            product.product_url
        ])

    # 컬럼 너비 조정
    ws.column_dimensions["A"].width = 8
    ws.column_dimensions["B"].width = 50
    ws.column_dimensions["C"].width = 20
    ws.column_dimensions["D"].width = 15
    ws.column_dimensions["E"].width = 15
    ws.column_dimensions["F"].width = 12
    ws.column_dimensions["G"].width = 50

    # 파일 저장
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"{keyword.keyword}_검색결과.xlsx"

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}"
        }
    )


@router.delete("/keywords/{keyword_id}")
async def delete_keyword(
    keyword_id: int,
    db: AsyncSession = Depends(get_db)
):
    """키워드 및 관련 데이터 삭제"""
    keyword = await db.get(Keyword, keyword_id)
    if not keyword:
        raise HTTPException(status_code=404, detail="키워드를 찾을 수 없습니다")

    await db.delete(keyword)
    await db.commit()

    return {"message": "삭제되었습니다"}
