from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models import Keyword, Product, RankingHistory
from app.schemas import SearchRequest, SearchResponse, ProductResponse
from app.services.naver_api import naver_api, NaverShoppingAPI
from app.services.crawler import phone_crawler

router = APIRouter(prefix="/api/search", tags=["search"])


@router.post("", response_model=SearchResponse)
async def search_products(
    request: SearchRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    키워드로 네이버 쇼핑 검색 및 저장
    """
    # 1. 기존 키워드 확인 또는 새로 생성
    result = await db.execute(
        select(Keyword).where(Keyword.keyword == request.keyword)
    )
    keyword_obj = result.scalar_one_or_none()

    if not keyword_obj:
        keyword_obj = Keyword(keyword=request.keyword)
        db.add(keyword_obj)
        await db.commit()
        await db.refresh(keyword_obj)

    # 2. 네이버 API로 상품 검색
    try:
        items = await naver_api.search_pages(
            keyword=request.keyword,
            start_page=request.start_page,
            end_page=request.end_page
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"네이버 API 오류: {str(e)}")

    # 3. 상품 저장 (기존 상품이면 업데이트, 없으면 새로 생성)
    products = []

    for item in items:
        parsed = NaverShoppingAPI.parse_product(item)

        # 기존 상품 확인 (같은 키워드 + 같은 naver_product_id)
        existing = await db.execute(
            select(Product).where(
                Product.keyword_id == keyword_obj.id,
                Product.naver_product_id == parsed["naver_product_id"]
            )
        )
        product = existing.scalar_one_or_none()

        if product:
            # 기존 상품 업데이트
            product.product_name = parsed["product_name"]
            product.price = parsed["price"]
            product.product_url = parsed["product_url"]
        else:
            # 새 상품 생성
            product = Product(
                keyword_id=keyword_obj.id,
                product_name=parsed["product_name"],
                product_url=parsed["product_url"],
                naver_product_id=parsed["naver_product_id"],
                product_image=parsed["product_image"],
                price=parsed["price"],
                store_name=parsed["store_name"],
                seller_name=parsed["seller_name"],
            )
            db.add(product)

        products.append((product, parsed["_rank"]))

    await db.commit()

    # 4. 순위 저장 (매번 새로 추가 - 시간 단위 기록)
    for product, rank in products:
        await db.refresh(product)
        ranking = RankingHistory(
            product_id=product.id,
            rank_position=rank
        )
        db.add(ranking)

    await db.commit()

    # 5. 전화번호 크롤링 (백그라운드)
    if request.crawl_phone:
        product_ids = [p.id for p, _ in products]
        background_tasks.add_task(crawl_phones_background, product_ids)

    # 6. 응답 생성
    product_responses = []
    for product, rank in products:
        product_responses.append(ProductResponse(
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
            current_rank=rank,
            rank_change=None
        ))

    return SearchResponse(
        keyword_id=keyword_obj.id,
        keyword=keyword_obj.keyword,
        total_products=len(products),
        products=product_responses
    )


async def crawl_phones_background(product_ids: List[int]):
    """백그라운드에서 전화번호 크롤링"""
    from app.database import async_session

    async with async_session() as db:
        # 상품 조회
        result = await db.execute(
            select(Product).where(Product.id.in_(product_ids))
        )
        products = result.scalars().all()

        # URL 목록 추출
        urls = [p.product_url for p in products if p.product_url]

        # 크롤링 실행
        phones = await phone_crawler.crawl_batch(urls)

        # 결과 업데이트
        for product, phone in zip(products, phones):
            if phone:
                product.phone_number = phone
                product.phone_crawled = 1
            else:
                product.phone_crawled = -1

        await db.commit()

    await phone_crawler.close_browser()
