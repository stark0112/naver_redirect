from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel


# ===== Keyword =====
class KeywordCreate(BaseModel):
    keyword: str


class KeywordResponse(BaseModel):
    id: int
    keyword: str
    created_at: datetime
    product_count: int = 0

    class Config:
        from_attributes = True


# ===== Product =====
class ProductBase(BaseModel):
    product_name: Optional[str] = None
    product_url: Optional[str] = None
    naver_product_id: Optional[str] = None
    product_image: Optional[str] = None
    price: Optional[int] = None
    store_name: Optional[str] = None
    seller_name: Optional[str] = None
    phone_number: Optional[str] = None


class ProductResponse(ProductBase):
    id: int
    keyword_id: int
    phone_crawled: int
    created_at: datetime
    current_rank: Optional[int] = None
    rank_change: Optional[int] = None  # 양수: 상승, 음수: 하락

    class Config:
        from_attributes = True


# ===== Ranking =====
class RankingResponse(BaseModel):
    date: date
    rank: int

    class Config:
        from_attributes = True


# ===== Search Request =====
class SearchRequest(BaseModel):
    keyword: str
    start_page: int = 1
    end_page: int = 1
    crawl_phone: bool = True  # 전화번호 크롤링 여부


# ===== Dashboard Stats =====
class DashboardStats(BaseModel):
    total_keywords: int
    total_products: int
    phone_success: int
    phone_failed: int
    today_crawled: int


# ===== API Response =====
class SearchResponse(BaseModel):
    keyword_id: int
    keyword: str
    total_products: int
    products: List[ProductResponse]
