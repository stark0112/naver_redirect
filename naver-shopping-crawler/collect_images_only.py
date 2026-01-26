"""
CAPTCHA 이미지만 수집 (풀지 않음)
- CAPTCHA 발생 → 이미지 저장 → 새로고침 → 반복
"""
import os
import time
from datetime import datetime
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By

# 이미지 저장 폴더
IMAGE_DIR = '/Users/teramime/Documents/project_20/naver-shopping-crawler/captcha_images'
os.makedirs(IMAGE_DIR, exist_ok=True)


def get_next_filename():
    """다음 파일명 생성"""
    existing = [f for f in os.listdir(IMAGE_DIR) if f.endswith('.png')]
    next_num = len(existing) + 1
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"captcha_{next_num:04d}_{timestamp}.png", next_num


def collect_captcha_images():
    """CAPTCHA 이미지 수집"""
    print("=" * 60)
    print("CAPTCHA 이미지 수집 (풀지 않음)")
    print("=" * 60)
    print(f"저장 위치: {IMAGE_DIR}")

    existing = [f for f in os.listdir(IMAGE_DIR) if f.endswith('.png')]
    print(f"기존 이미지: {len(existing)}개\n")

    # 브라우저 설정
    options = uc.ChromeOptions()
    options.add_argument('--no-sandbox')

    print("[1] 브라우저 시작...")
    driver = uc.Chrome(options=options, version_main=143)

    # 네이버 로그인
    print("\n[2] 네이버 로그인")
    driver.get("https://nid.naver.com/nidlogin.login")
    print("   브라우저에서 직접 로그인해주세요.")
    input("   로그인 완료 후 Enter 키를 누르세요...")

    # 상품 URL
    product_url = "https://smartstore.naver.com/main/products/7255034137"
    collected = 0

    try:
        while True:
            print(f"\n[3] 페이지 이동: {product_url}")
            driver.get(product_url)
            time.sleep(2)

            # 판매자 정보 버튼 클릭
            print("[4] '판매자 상세정보' 버튼 클릭...")
            try:
                seller_btn = driver.find_element(By.CSS_SELECTOR, "a._26MYJfApxOCz0o0S9g3HtD")
                seller_btn.click()
                time.sleep(2)
            except:
                links = driver.find_elements(By.TAG_NAME, 'a')
                for link in links:
                    text = link.text or ''
                    if '판매자' in text and '상세' in text:
                        link.click()
                        time.sleep(2)
                        break

            # CAPTCHA 이미지 영역 찾기 및 저장
            print("[5] CAPTCHA 이미지 캡처...")

            try:
                # CAPTCHA 이미지 요소 찾기
                captcha_img = None
                selectors = [
                    "img[src*='captcha']",
                    ".captcha_image img",
                    "img[alt*='보안']",
                    ".captcha img",
                    "img"
                ]

                for selector in selectors:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        for elem in elements:
                            src = elem.get_attribute('src') or ''
                            if 'captcha' in src.lower() or elem.size['width'] > 200:
                                captcha_img = elem
                                break
                        if captcha_img:
                            break
                    except:
                        continue

                # 이미지 저장
                filename, num = get_next_filename()
                filepath = os.path.join(IMAGE_DIR, filename)

                if captcha_img:
                    captcha_img.screenshot(filepath)
                    print(f"   ✅ CAPTCHA 이미지 저장: {filename}")
                else:
                    # 전체 화면 캡처
                    driver.save_screenshot(filepath)
                    print(f"   ✅ 전체 화면 저장: {filename}")

                collected += 1
                print(f"   총 수집: {num}개")

            except Exception as e:
                print(f"   ❌ 캡처 실패: {e}")

            # 다음 동작
            print("\n" + "-" * 40)
            print("  Enter: 새로고침 (새 CAPTCHA)")
            print("  q: 종료")
            print("-" * 40)

            action = input("  선택: ").strip().lower()

            if action == 'q':
                break

    except KeyboardInterrupt:
        print("\n\n중단!")

    finally:
        total = len([f for f in os.listdir(IMAGE_DIR) if f.endswith('.png')])
        print(f"\n{'=' * 60}")
        print(f"이번 세션 수집: {collected}개")
        print(f"전체 이미지: {total}개")
        print(f"저장 위치: {IMAGE_DIR}")
        print('=' * 60)
        driver.quit()


if __name__ == "__main__":
    collect_captcha_images()
