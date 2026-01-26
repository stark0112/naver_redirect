import httpx
from typing import List, Dict, Any, Optional
from app.config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET


class NaverShoppingAPI:
    """네이버 쇼핑 검색 API 클라이언트"""

    BASE_URL = "https://openapi.naver.com/v1/search/shop.json"

    def __init__(self):
        self.headers = {
            "X-Naver-Client-Id": NAVER_CLIENT_ID,
            "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
        }

    async def search(
        self,
        keyword: str,
        display: int = 100,
        start: int = 1,
        sort: str = "sim"  # sim: 정확도순, date: 날짜순, asc: 가격오름차순, dsc: 가격내림차순
    ) -> Dict[str, Any]:
        """
        네이버 쇼핑 검색 API 호출

        Args:
            keyword: 검색어
            display: 한 번에 표시할 검색 결과 개수 (최대 100)
            start: 검색 시작 위치 (최대 1000)
            sort: 정렬 기준

        Returns:
            API 응답 데이터
        """
        params = {
            "query": keyword,
            "display": min(display, 100),
            "start": min(start, 1000),
            "sort": sort,
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.BASE_URL,
                headers=self.headers,
                params=params,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()

    async def search_pages(
        self,
        keyword: str,
        start_page: int = 1,
        end_page: int = 1,
        per_page: int = 100
    ) -> List[Dict[str, Any]]:
        """
        여러 페이지 검색 결과 가져오기

        Args:
            keyword: 검색어
            start_page: 시작 페이지 (1부터)
            end_page: 끝 페이지
            per_page: 페이지당 결과 수

        Returns:
            상품 목록 (순위 정보 포함)
        """
        all_products = []
        rank = (start_page - 1) * per_page + 1

        for page in range(start_page, end_page + 1):
            start = (page - 1) * per_page + 1

            # API 제한: start는 최대 1000
            if start > 1000:
                break

            try:
                result = await self.search(keyword, display=per_page, start=start)
                items = result.get("items", [])

                for item in items:
                    item["_rank"] = rank
                    item["_page"] = page
                    rank += 1
                    all_products.append(item)

            except httpx.HTTPStatusError as e:
                print(f"API 오류 (페이지 {page}): {e}")
                break

        return all_products

    @staticmethod
    def parse_product(item: Dict[str, Any]) -> Dict[str, Any]:
        """
        API 응답 아이템을 Product 모델 형식으로 변환

        Args:
            item: API 응답의 개별 아이템

        Returns:
            Product 모델에 맞는 딕셔너리
        """
        # HTML 태그 제거 (제목에 <b> 태그가 포함됨)
        title = item.get("title", "")
        title = title.replace("<b>", "").replace("</b>", "")

        # productId 직접 사용 (API에서 제공)
        product_id = str(item.get("productId", ""))

        return {
            "product_name": title,
            "product_url": item.get("link", ""),
            "naver_product_id": product_id,
            "product_image": item.get("image", ""),
            "price": int(item.get("lprice", 0)),
            "store_name": item.get("mallName", ""),
            "seller_name": item.get("maker", "") or item.get("brand", ""),
            "_rank": item.get("_rank", 0),
        }


# 싱글톤 인스턴스
naver_api = NaverShoppingAPI()
