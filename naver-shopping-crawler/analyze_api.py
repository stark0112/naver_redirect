"""
네이버 스마트스토어 API 분석
- 판매자 정보를 가져오는 API 엔드포인트가 있는지 확인
"""
import requests
import json
import re

def analyze_smartstore_api(product_url):
    """스마트스토어 상품 페이지에서 API 엔드포인트 분석"""

    print(f"[1] 상품 URL 분석: {product_url}")

    # URL에서 상품 ID 추출
    # https://smartstore.naver.com/main/products/7255034137
    match = re.search(r'/products/(\d+)', product_url)
    if match:
        product_id = match.group(1)
        print(f"    상품 ID: {product_id}")
    else:
        print("    상품 ID를 찾을 수 없음")
        return

    # 스토어명 추출
    store_match = re.search(r'smartstore\.naver\.com/([^/]+)', product_url)
    store_name = store_match.group(1) if store_match else 'main'
    print(f"    스토어명: {store_name}")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': product_url,
    }

    # 가능한 API 엔드포인트들
    api_endpoints = [
        # 상품 정보 API
        f"https://smartstore.naver.com/i/v1/stores/{store_name}/products/{product_id}",
        f"https://smartstore.naver.com/i/v1/products/{product_id}",
        f"https://smartstore.naver.com/api/products/{product_id}",

        # 스토어/판매자 정보 API
        f"https://smartstore.naver.com/i/v1/stores/{store_name}",
        f"https://smartstore.naver.com/i/v1/stores/{store_name}/info",
        f"https://smartstore.naver.com/api/stores/{store_name}",

        # 네이버 쇼핑 API
        f"https://search.shopping.naver.com/api/search/all?query={product_id}",

        # 판매자 상세 정보 (CAPTCHA 필요할 수 있음)
        f"https://smartstore.naver.com/i/v1/stores/{store_name}/seller",
        f"https://smartstore.naver.com/i/v1/stores/{store_name}/business-info",
    ]

    print(f"\n[2] API 엔드포인트 테스트 ({len(api_endpoints)}개)")

    for i, endpoint in enumerate(api_endpoints):
        print(f"\n    [{i+1}] {endpoint}")
        try:
            resp = requests.get(endpoint, headers=headers, timeout=10)
            print(f"        상태: {resp.status_code}")

            if resp.status_code == 200:
                try:
                    data = resp.json()
                    # 주요 키 출력
                    if isinstance(data, dict):
                        keys = list(data.keys())[:10]
                        print(f"        키: {keys}")

                        # 전화번호 관련 필드 찾기
                        json_str = json.dumps(data, ensure_ascii=False)
                        if '전화' in json_str or 'phone' in json_str.lower() or 'tel' in json_str.lower():
                            print("        ★ 전화번호 관련 데이터 발견!")

                            # 전화번호 패턴 검색
                            phones = re.findall(r'\d{2,4}-\d{3,4}-\d{4}', json_str)
                            if phones:
                                print(f"        ★ 전화번호: {phones}")

                        # 판매자 정보 관련 필드
                        if 'seller' in json_str.lower() or '판매자' in json_str:
                            print("        ★ 판매자 정보 발견!")

                except json.JSONDecodeError:
                    print(f"        (HTML 응답, {len(resp.text)}자)")

            elif resp.status_code == 403:
                print("        접근 거부 (인증 필요)")
            elif resp.status_code == 404:
                print("        엔드포인트 없음")

        except Exception as e:
            print(f"        오류: {e}")

    # 상품 페이지 HTML에서 API 호출 분석
    print(f"\n[3] 상품 페이지 HTML 분석")
    try:
        resp = requests.get(product_url, headers=headers, timeout=10)
        html = resp.text

        # script 태그에서 초기 데이터 추출
        # __PRELOADED_STATE__ 또는 window.__INITIAL_STATE__ 패턴
        state_match = re.search(r'__PRELOADED_STATE__\s*=\s*(\{.+?\});', html, re.DOTALL)
        if state_match:
            print("    __PRELOADED_STATE__ 발견!")
            try:
                state_data = json.loads(state_match.group(1))
                print(f"    키: {list(state_data.keys())[:10]}")

                # 판매자 정보 찾기
                json_str = json.dumps(state_data, ensure_ascii=False)
                if '전화' in json_str or 'phone' in json_str.lower():
                    print("    ★ 전화번호 관련 데이터 있음!")

                    # 전화번호 추출
                    phones = re.findall(r'\d{2,4}-\d{3,4}-\d{4}', json_str)
                    if phones:
                        print(f"    ★ 전화번호: {set(phones)}")

            except json.JSONDecodeError as e:
                print(f"    JSON 파싱 실패: {e}")

        # API URL 패턴 찾기
        api_urls = re.findall(r'https?://[^\s"\']+api[^\s"\']*', html)
        if api_urls:
            print(f"\n    API URL 패턴 발견 ({len(set(api_urls))}개):")
            for url in list(set(api_urls))[:10]:
                print(f"      - {url[:100]}")

    except Exception as e:
        print(f"    오류: {e}")


def test_shopping_api():
    """네이버 쇼핑 검색 API 테스트"""
    print("\n" + "=" * 60)
    print("[4] 네이버 쇼핑 검색 API 테스트")
    print("=" * 60)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'application/json',
    }

    # 네이버 쇼핑 검색 API
    search_url = "https://search.shopping.naver.com/api/search/all"
    params = {
        'query': '아이폰',
        'sort': 'rel',
        'pagingIndex': 1,
        'pagingSize': 10,
    }

    try:
        resp = requests.get(search_url, params=params, headers=headers, timeout=10)
        print(f"상태: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            print(f"키: {list(data.keys())}")

            # 상품 목록에서 판매자 정보 확인
            if 'shoppingResult' in data:
                products = data['shoppingResult'].get('products', [])
                print(f"상품 수: {len(products)}")

                if products:
                    first = products[0]
                    print(f"첫 상품 키: {list(first.keys())}")

                    # 판매자 관련 필드
                    seller_fields = ['mallName', 'seller', 'mallNo', 'sellerNo']
                    for field in seller_fields:
                        if field in first:
                            print(f"  {field}: {first[field]}")

    except Exception as e:
        print(f"오류: {e}")


if __name__ == "__main__":
    # 테스트 URL
    test_url = "https://smartstore.naver.com/main/products/7255034137"

    print("=" * 60)
    print("네이버 스마트스토어 API 분석")
    print("=" * 60)

    analyze_smartstore_api(test_url)
    test_shopping_api()
