"""
botasaurus 테스트 - 네이버 스마트스토어 봇 탐지 우회 확인
"""
from botasaurus.browser import browser, Driver
from botasaurus.soupify import soupify
import time

@browser(
    headless=False,  # 브라우저 창 표시 (테스트용)
    block_images=False,
    wait_for_complete_page_load=True,
)
def test_naver_smartstore(driver: Driver, url: str):
    """네이버 스마트스토어 접속 테스트"""
    print(f"\n[1] URL 접속: {url}")
    driver.get(url)
    time.sleep(3)

    # 페이지 타이틀 확인
    title = driver.title
    print(f"[2] 페이지 타이틀: {title}")

    # 판매자 정보 버튼 찾기
    print("[3] '판매자 상세정보 확인' 버튼 찾기...")

    try:
        # CSS 선택자로 버튼 찾기
        seller_btn = driver.get_element_or_none("a._26MYJfApxOCz0o0S9g3HtD")
        if seller_btn:
            print("   → 버튼 발견!")
            seller_btn.click()
            print("   → 버튼 클릭!")
            time.sleep(3)

            # CAPTCHA 확인
            page_source = driver.page_html
            if 'captcha' in page_source.lower() or '영수증' in page_source:
                print("   → CAPTCHA 발생!")
            else:
                print("   → CAPTCHA 없음 (우회 성공?)")

            # 전화번호 찾기
            if '전화번호' in page_source or 'tel:' in page_source:
                print("   → 전화번호 정보 발견!")
        else:
            print("   → 버튼을 찾을 수 없음")

            # 다른 방법 시도
            all_links = driver.get_elements("a")
            for link in all_links:
                text = link.text or ""
                if "판매자" in text and "상세" in text:
                    print(f"   → 대체 버튼 발견: {text}")
                    link.click()
                    time.sleep(3)
                    break

    except Exception as e:
        print(f"   → 오류: {e}")

    # 스크린샷 저장
    driver.save_screenshot("/tmp/botasaurus_test.png")
    print("[4] 스크린샷 저장: /tmp/botasaurus_test.png")

    # 잠시 대기 (수동 확인용)
    print("[5] 10초 대기 (화면 확인)...")
    time.sleep(10)

    return {"title": title}


if __name__ == "__main__":
    # 테스트 URL
    test_url = "https://smartstore.naver.com/main/products/7255034137"

    print("=" * 60)
    print("botasaurus 네이버 스마트스토어 테스트")
    print("=" * 60)

    result = test_naver_smartstore(test_url)
    print(f"\n결과: {result}")
