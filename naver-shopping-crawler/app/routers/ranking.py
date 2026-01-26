from datetime import date, timedelta
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.database import get_db
from app.models import Product, RankingHistory
from app.schemas import RankingResponse

router = APIRouter(prefix="/api/ranking", tags=["ranking"])


@router.get("/product/{product_id}", response_model=List[RankingResponse])
async def get_product_ranking_history(
    product_id: int,
    days: int = 30,
    db: AsyncSession = Depends(get_db)
):
    """특정 상품의 순위 히스토리 조회"""
    # 상품 확인
    product = await db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다")

    # 최근 N일 순위 조회
    start_date = date.today() - timedelta(days=days)

    result = await db.execute(
        select(RankingHistory)
        .where(
            and_(
                RankingHistory.product_id == product_id,
                RankingHistory.recorded_at >= start_date
            )
        )
        .order_by(RankingHistory.recorded_at)
    )
    rankings = result.scalars().all()

    return [
        RankingResponse(
            date=r.recorded_at,
            rank=r.rank_position
        )
        for r in rankings
    ]


@router.get("/drops")
async def get_ranking_drops(
    keyword_id: int,
    min_drop: int = 5,
    db: AsyncSession = Depends(get_db)
):
    """
    순위 하락 상품 조회 (영업 타겟)
    최신 검색 vs 이전 검색 비교

    Args:
        keyword_id: 키워드 ID
        min_drop: 최소 하락 순위 (기본 5)

    Returns:
        순위 하락 상품 목록
    """
    # 해당 키워드의 상품들 조회
    result = await db.execute(
        select(Product)
        .where(Product.keyword_id == keyword_id)
    )
    products = result.scalars().all()

    drops = []

    for product in products:
        # 최근 3개의 순위 기록 조회 (최신순)
        rankings_result = await db.execute(
            select(RankingHistory)
            .where(RankingHistory.product_id == product.id)
            .order_by(RankingHistory.recorded_at.desc())
            .limit(3)
        )
        rankings = rankings_result.scalars().all()

        if len(rankings) >= 2:
            current_ranking = rankings[0]  # 최신 (3회차)
            previous_ranking = rankings[1]  # 이전 (2회차)
            oldest_ranking = rankings[2] if len(rankings) >= 3 else None  # 그 이전 (1회차)

            # 순위 하락 = 현재 순위 - 이전 순위 (양수면 하락)
            drop = current_ranking.rank_position - previous_ranking.rank_position

            if drop >= min_drop:
                drops.append({
                    "product_id": product.id,
                    "product_name": product.product_name,
                    "store_name": product.store_name,
                    "phone_number": product.phone_number,
                    "rank_1": oldest_ranking.rank_position if oldest_ranking else None,
                    "time_1": oldest_ranking.recorded_at.strftime("%m/%d %H:%M") if oldest_ranking else None,
                    "rank_2": previous_ranking.rank_position,
                    "time_2": previous_ranking.recorded_at.strftime("%m/%d %H:%M"),
                    "rank_3": current_ranking.rank_position,
                    "time_3": current_ranking.recorded_at.strftime("%m/%d %H:%M"),
                    "drop": drop
                })

    # 하락 순으로 정렬
    drops.sort(key=lambda x: x["drop"], reverse=True)

    return drops
