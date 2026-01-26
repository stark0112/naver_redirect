"""
네이버 스마트스토어 API 분석 v2
- 더 정교한 헤더와 세션 사용
"""
import requests
import json
import re
import time

def create_session():
    """브라우저처럼 보이는 세션 생성"""
    session = requests.Session()

    # 실제 브라우저와 유사한 헤더
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    })

    return session


def analyze_with_session(product_url):
    """세션을 사용해서 분석"""
    session = create_session()

    print(f"[1] 먼저 메인 페이지 방문 (쿠키 획득)")

    # 1. 네이버 메인 방문
    try:
        resp = session.get('https://www.naver.com', timeout=10)
        print(f"    네이버 메인: {resp.status_code}")
        time.sleep(1)
    except Exception as e:
        print(f"    오류: {e}")

    # 2. 스마트스토어 메인 방문
    try:
        resp = session.get('https://smartstore.naver.com', timeout=10)
        print(f"    스마트스토어 메인: {resp.status_code}")
        time.sleep(1)
    except Exception as e:
        print(f"    오류: {e}")

    # 3. 상품 페이지 방문
    print(f"\n[2] 상품 페이지 방문: {product_url}")
    try:
        resp = session.get(product_url, timeout=10)
        print(f"    상태: {resp.status_code}")
        print(f"    쿠키: {list(session.cookies.keys())}")

        html = resp.text

        # __PRELOADED_STATE__ 찾기
        print(f"\n[3] HTML 분석 ({len(html)}자)")

        # 여러 패턴 시도
        patterns = [
            r'window\.__PRELOADED_STATE__\s*=\s*(\{.+?\});\s*</script>',
            r'__PRELOADED_STATE__\s*=\s*"(.+?)"',
            r'"product"\s*:\s*(\{.+?"id".+?\})',
            r'"channel"\s*:\s*(\{.+?\})',
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.DOTALL)
            if match:
                print(f"    패턴 매칭: {pattern[:50]}...")
                try:
                    data_str = match.group(1)
                    # escape된 JSON 처리
                    if data_str.startswith('"'):
                        data_str = json.loads('"' + data_str + '"')
                    data = json.loads(data_str)
                    print(f"    키: {list(data.keys())[:5]}")
                except:
                    print(f"    (파싱 실패)")

        # 판매자 관련 텍스트 검색
        seller_patterns = [
            (r'"sellerNo"\s*:\s*"?(\d+)"?', 'sellerNo'),
            (r'"mallNo"\s*:\s*"?(\d+)"?', 'mallNo'),
            (r'"channelNo"\s*:\s*"?(\d+)"?', 'channelNo'),
            (r'"representPhoneNo"\s*:\s*"([^"]+)"', 'representPhoneNo'),
            (r'"phoneNo"\s*:\s*"([^"]+)"', 'phoneNo'),
            (r'"tel"\s*:\s*"([^"]+)"', 'tel'),
            (r'(\d{2,4}-\d{3,4}-\d{4})', '전화번호 패턴'),
        ]

        print(f"\n[4] 판매자 정보 검색")
        found_info = {}
        for pattern, name in seller_patterns:
            matches = re.findall(pattern, html)
            if matches:
                unique = list(set(matches))[:3]
                found_info[name] = unique
                print(f"    {name}: {unique}")

        # channel 정보로 판매자 API 호출 시도
        if 'channelNo' in found_info:
            channel_no = found_info['channelNo'][0]
            print(f"\n[5] 채널 API 시도 (channelNo: {channel_no})")

            # API 헤더 업데이트
            session.headers.update({
                'Accept': 'application/json, text/plain, */*',
                'Referer': product_url,
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
            })

            api_urls = [
                f"https://smartstore.naver.com/i/v1/channels/{channel_no}",
                f"https://smartstore.naver.com/i/v1/channels/{channel_no}/info",
                f"https://smartstore.naver.com/i/v1/channels/{channel_no}/seller",
            ]

            for api_url in api_urls:
                time.sleep(0.5)
                try:
                    resp = session.get(api_url, timeout=10)
                    print(f"    {api_url.split('/')[-1]}: {resp.status_code}")

                    if resp.status_code == 200:
                        try:
                            data = resp.json()
                            print(f"      키: {list(data.keys())[:5]}")

                            # 전화번호 찾기
                            json_str = json.dumps(data, ensure_ascii=False)
                            phones = re.findall(r'\d{2,4}-\d{3,4}-\d{4}', json_str)
                            if phones:
                                print(f"      ★ 전화번호: {set(phones)}")
                        except:
                            pass
                except Exception as e:
                    print(f"    오류: {e}")

        return found_info

    except Exception as e:
        print(f"    오류: {e}")
        return {}


def search_naver_shopping(keyword):
    """네이버 쇼핑에서 상품 검색 후 판매자 정보 확인"""
    print(f"\n{'='*60}")
    print(f"[6] 네이버 쇼핑 검색: {keyword}")
    print('='*60)

    session = create_session()

    # 네이버 쇼핑 검색 페이지 방문
    search_url = f"https://search.shopping.naver.com/search/all?query={keyword}"

    try:
        resp = session.get(search_url, timeout=10)
        print(f"상태: {resp.status_code}")

        html = resp.text

        # __NEXT_DATA__ 찾기 (Next.js 앱)
        next_data = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.+?)</script>', html)
        if next_data:
            print("__NEXT_DATA__ 발견!")
            try:
                data = json.loads(next_data.group(1))
                print(f"키: {list(data.keys())}")

                # props > pageProps > initialState > products
                props = data.get('props', {}).get('pageProps', {})
                print(f"pageProps 키: {list(props.keys())[:10]}")

                # 상품 데이터 찾기
                if 'initialState' in props:
                    state = props['initialState']
                    if 'products' in state:
                        products = state['products'].get('list', [])
                        print(f"상품 수: {len(products)}")

                        if products:
                            first = products[0]
                            print(f"첫 상품 키: {list(first.keys())}")

                            # 판매자 정보
                            for key in ['mallName', 'mallNo', 'channel', 'seller', 'sellerNo']:
                                if key in first:
                                    print(f"  {key}: {first[key]}")

            except json.JSONDecodeError as e:
                print(f"JSON 파싱 실패: {e}")

    except Exception as e:
        print(f"오류: {e}")


if __name__ == "__main__":
    test_url = "https://smartstore.naver.com/main/products/7255034137"

    print("=" * 60)
    print("네이버 스마트스토어 API 분석 v2")
    print("=" * 60)

    info = analyze_with_session(test_url)

    # 네이버 쇼핑 검색도 테스트
    search_naver_shopping("아이폰 케이스")
