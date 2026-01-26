from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Text, DateTime, Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class Keyword(Base):
    """검색 키워드"""
    __tablename__ = "keywords"

    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword = Column(String(255), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    products = relationship("Product", back_populates="keyword", cascade="all, delete-orphan")


class Product(Base):
    """상품/판매자 정보"""
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword_id = Column(Integer, ForeignKey("keywords.id"), nullable=False)

    # 상품 정보
    product_name = Column(Text)
    product_url = Column(Text)
    naver_product_id = Column(String(100), index=True)
    product_image = Column(Text)
    price = Column(Integer)

    # 판매자 정보
    store_name = Column(String(255))
    seller_name = Column(String(255))
    phone_number = Column(String(50))

    # 크롤링 상태
    phone_crawled = Column(Integer, default=0)  # 0: 미시도, 1: 성공, -1: 실패

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    keyword = relationship("Keyword", back_populates="products")
    rankings = relationship("RankingHistory", back_populates="product", cascade="all, delete-orphan")


class RankingHistory(Base):
    """순위 히스토리"""
    __tablename__ = "ranking_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    rank_position = Column(Integer, nullable=False)
    recorded_at = Column(DateTime, default=datetime.utcnow)  # 시간 단위로 변경

    product = relationship("Product", back_populates="rankings")
