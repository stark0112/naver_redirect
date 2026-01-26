"""
기존 크롤러 로직 활용 - CAPTCHA 이미지만 수집
버튼 클릭 → Enter 누르면 저장 → 반복
"""
import os
import time
from datetime import datetime
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 설정
COOKIE_FILE = '/tmp/naver_cookies.json'
IMAGE_DIR = '/Users/teramime/Documents/project_20/naver-shopping-crawler/captcha_images'
os.makedirs(IMAGE_DIR, exist_ok=True)


def save_captcha_image(driver):
    """CAPTCHA 이미지 저장"""
    existing = [f for f in os.listdir(IMAGE_DIR) if f.endswith('.png')]
    next_num = len(existing) + 1
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"captcha_{next_num:04d}_{timestamp}.png"
    filepath = os.path.join(IMAGE_DIR, filename)

    # 전체 화면 캡처
    driver.save_screenshot(filepath)
    print(f"   ✅ 저장: {filename} (총 {next_num}개)")
    return next_num


def main():
    print("=" * 60)
    print("CAPTCHA 이미지 수집 (기존 크롤러 방식)")
    print("=" * 60)

    existing = [f for f in os.listdir(IMAGE_DIR) if f.endswith('.png')]
    print(f"저장 위치: {IMAGE_DIR}")
    print(f"기존 이미지: {len(existing)}개\n")

    # 브라우저 시작
    options = uc.ChromeOptions()
    options.add_argument('--no-sandbox')

    print("[1] 브라우저 시작...")
    driver = uc.Chrome(options=options, version_main=143)

    # 로그인
    print("[2] 네이버 로그인...")
    driver.get("https://nid.naver.com/nidlogin.login")
    input("   로그인 후 Enter...")

    # 상품 URL (원하면 변경 가능)
    product_url = "https://smartstore.naver.com/main/products/7255034137"

    try:
        while True:
            # 상품 페이지 이동
            print(f"\n[3] 상품 페이지 이동...")
            driver.get(product_url)
            time.sleep(2)

            # 판매자 정보 버튼 클릭
            print("[4] 판매자 상세정보 버튼 클릭...")
            clicked = False

            # 방법 1: CSS 선택자
            try:
                btn = driver.find_element(By.CSS_SELECTOR, "a._26MYJfApxOCz0o0S9g3HtD")
                btn.click()
                clicked = True
            except:
                pass

            # 방법 2: 텍스트로 찾기
            if not clicked:
                try:
                    links = driver.find_elements(By.TAG_NAME, 'a')
                    for link in links:
                        text = link.text or ''
                        if '판매자' in text and '상세' in text:
                            link.click()
                            clicked = True
                            break
                except:
                    pass

            if clicked:
                print("   버튼 클릭 완료!")
            else:
                print("   버튼을 찾지 못함")

            time.sleep(2)

            # 사용자 입력 대기
            print("\n" + "-" * 40)
            print("  Enter: 이미지 저장")
            print("  r: 새로고침")
            print("  u: 새 URL 입력")
            print("  q: 종료")
            print("-" * 40)

            action = input("  >> ").strip().lower()

            if action == 'q':
                break
            elif action == 'r':
                continue  # 다시 루프
            elif action == 'u':
                new_url = input("  새 URL: ").strip()
                if new_url:
                    product_url = new_url
                continue
            else:  # Enter
                save_captcha_image(driver)

    except KeyboardInterrupt:
        print("\n중단!")

    finally:
        total = len([f for f in os.listdir(IMAGE_DIR) if f.endswith('.png')])
        print(f"\n총 수집: {total}개")
        driver.quit()


if __name__ == "__main__":
    main()
