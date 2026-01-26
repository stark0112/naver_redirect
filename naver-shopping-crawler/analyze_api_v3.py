"""
네이버 스마트스토어 - HTML에서 직접 전화번호 추출 테스트
"""
import requests
import json
import re
import time

def extract_seller_info(product_url):
    """상품 페이지 HTML에서 판매자 정보 추출"""

    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9',
    })

    # 쿠키 획득을 위해 메인 먼저 방문
    session.get('https://smartstore.naver.com', timeout=10)
    time.sleep(0.5)

    # 상품 페이지 방문
    print(f"[1] 상품 페이지: {product_url}")
    resp = session.get(product_url, timeout=10)
    print(f"    상태: {resp.status_code}")

    html = resp.text
    print(f"    HTML 길이: {len(html)}자")

    # HTML 일부 저장 (디버깅용)
    with open('/tmp/smartstore_page.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"    HTML 저장: /tmp/smartstore_page.html")

    # 판매자 정보 추출
    print(f"\n[2] 판매자 정보 추출")

    info = {}

    # 1. 전화번호 패턴
    phones = re.findall(r'\d{2,4}-\d{3,4}-\d{4}', html)
    if phones:
        info['전화번호'] = list(set(phones))
        print(f"    전화번호: {info['전화번호']}")

    # 2. 스토어명
    store_match = re.search(r'"storeName"\s*:\s*"([^"]+)"', html)
    if store_match:
        info['스토어명'] = store_match.group(1)
        print(f"    스토어명: {info['스토어명']}")

    # 3. 판매자 이름
    seller_match = re.search(r'"representativeName"\s*:\s*"([^"]+)"', html)
    if seller_match:
        info['대표자명'] = seller_match.group(1)
        print(f"    대표자명: {info['대표자명']}")

    # 4. 사업자번호
    biz_match = re.search(r'"businessRegistrationNumber"\s*:\s*"([^"]+)"', html)
    if biz_match:
        info['사업자번호'] = biz_match.group(1)
        print(f"    사업자번호: {info['사업자번호']}")

    # 5. 채널/스토어 번호
    channel_match = re.search(r'"channelNo"\s*:\s*"?(\d+)"?', html)
    if channel_match:
        info['channelNo'] = channel_match.group(1)
        print(f"    channelNo: {info['channelNo']}")

    # 6. JSON 데이터 블록 찾기
    print(f"\n[3] JSON 데이터 분석")

    # script 태그 내 JSON 찾기
    script_pattern = r'<script[^>]*>([^<]*\{[^<]*"channel"[^<]*\}[^<]*)</script>'
    scripts = re.findall(script_pattern, html, re.DOTALL)
    print(f"    channel 포함 script 블록: {len(scripts)}개")

    # __PRELOADED_STATE__ 찾기
    preload_patterns = [
        r'window\.__PRELOADED_STATE__\s*=\s*({.+?});?\s*(?:</script>|window\.)',
        r'__PRELOADED_STATE__\s*=\s*({.+?});',
    ]

    for pattern in preload_patterns:
        match = re.search(pattern, html, re.DOTALL)
        if match:
            print(f"    __PRELOADED_STATE__ 발견!")
            try:
                json_str = match.group(1)
                # 줄바꿈 제거
                json_str = json_str.replace('\n', '').replace('\r', '')
                data = json.loads(json_str)
                print(f"    최상위 키: {list(data.keys())}")

                # channel 정보 찾기
                if 'channel' in data:
                    channel = data['channel']
                    print(f"    channel 키: {list(channel.keys()) if isinstance(channel, dict) else type(channel)}")

                # 판매자 정보 깊이 탐색
                def find_phone_recursive(obj, path=""):
                    if isinstance(obj, dict):
                        for k, v in obj.items():
                            if 'phone' in k.lower() or 'tel' in k.lower() or '전화' in k:
                                print(f"      [{path}.{k}]: {v}")
                            find_phone_recursive(v, f"{path}.{k}")
                    elif isinstance(obj, list) and len(obj) < 10:
                        for i, item in enumerate(obj):
                            find_phone_recursive(item, f"{path}[{i}]")

                print(f"\n    전화번호 관련 필드 검색:")
                find_phone_recursive(data)

            except json.JSONDecodeError as e:
                print(f"    JSON 파싱 실패: {e}")
            break

    return info


def test_multiple_products():
    """여러 상품 페이지에서 전화번호 추출 테스트"""
    print("\n" + "=" * 60)
    print("[4] 여러 상품 테스트")
    print("=" * 60)

    # 다른 스마트스토어 상품들
    test_urls = [
        "https://smartstore.naver.com/main/products/7255034137",
        # 다른 스토어들도 테스트 가능
    ]

    for url in test_urls:
        print(f"\n--- {url} ---")
        info = extract_seller_info(url)
        print(f"추출된 정보: {info}")
        time.sleep(2)  # rate limit 방지


if __name__ == "__main__":
    # 단일 상품 테스트
    test_url = "https://smartstore.naver.com/main/products/7255034137"
    info = extract_seller_info(test_url)

    print("\n" + "=" * 60)
    print("최종 결과")
    print("=" * 60)
    print(json.dumps(info, ensure_ascii=False, indent=2))
