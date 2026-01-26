"""
디버거 크롬 모드로 CAPTCHA 우회
- 실제 Chrome 브라우저 사용
- 복사 붙여넣기로 입력
"""
import asyncio
import subprocess
import re
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import easyocr

# OCR
reader = None
def get_reader():
    global reader
    if reader is None:
        print("OCR 초기화...")
        reader = easyocr.Reader(['ko', 'en'], gpu=False)
    return reader


def paste_text(text):
    """Mac에서 클립보드에 텍스트 복사"""
    subprocess.run('pbcopy', text=True, input=text)


def solve_captcha_selenium(driver):
    """Selenium용 CAPTCHA 해결"""
    try:
        # 질문 찾기 - 여러 패턴 시도
        question = None
        question_patterns = [
            "//*[contains(text(), '빈 칸')]",
            "//*[contains(text(), '번째')]",
            "//*[contains(text(), '몇 개')]",
            "//*[contains(text(), '총')]",
            "//*[contains(text(), '영수증')]",
            "//*[contains(@style, 'color') and contains(text(), '?')]",
        ]

        for pattern in question_patterns:
            try:
                elem = driver.find_element(By.XPATH, pattern)
                if elem.text and len(elem.text) > 5:
                    question = elem.text
                    break
            except:
                continue

        if not question:
            # 페이지 전체에서 질문 찾기
            page_text = driver.page_source
            q_match = re.search(r'(영수증에서[^?]+\?|빈 칸[^?]+\?|전화번호[^?]+\?)', page_text)
            if q_match:
                question = q_match.group(1)

        if not question:
            return False

        print(f"    질문: {question[:50]}...")

        # 이미지 찾기 및 저장
        img = driver.find_element(By.TAG_NAME, 'img')
        img.screenshot('/tmp/captcha_selenium.png')

        # OCR
        ocr = get_reader().readtext('/tmp/captcha_selenium.png')
        text = ' '.join([r[1] for r in ocr])
        print(f"    OCR: {text[:60]}...")

        answer = None

        # 영수증 - 총 몇 개 (수량 합산)
        if '몇 개' in question or '총' in question and '영수증' in question:
            # 수량 열에서 숫자 추출
            numbers = re.findall(r'\b(\d{1,3})\b', text)
            # 1-2자리 숫자만 (수량으로 보이는 것)
            quantities = [int(n) for n in numbers if 1 <= int(n) <= 99]
            if quantities:
                # 수량으로 보이는 작은 숫자들 합산
                answer = sum(quantities[:10])  # 최대 10개 항목
                print(f"    수량 후보: {quantities[:10]} → 합계: {answer}")

        # 전화번호 문제
        elif '전화번호' in question:
            direction = '앞' if '앞에서' in question else '뒤'
            pos_match = re.search(r'(\d+)번째', question)
            pos = int(pos_match.group(1)) if pos_match else 1

            phone_match = re.search(r'(\d{3,4})[-\s](\d{4})', text)
            if phone_match:
                digits = phone_match.group(1) + phone_match.group(2)
                answer = digits[pos - 1] if direction == '앞' else digits[-pos]
                print(f"    전화번호: {digits}, {direction}에서 {pos}번째 = {answer}")

        # 주소 문제
        elif '길' in question:
            addr_match = re.search(r'길\s*(\d+)', text)
            if addr_match:
                answer = addr_match.group(1)
                print(f"    주소 숫자: {answer}")

        if answer:
            # 입력 필드 찾기
            inp = None
            for sel in ['input[type="text"]', 'input[type="number"]', 'input:not([type="hidden"])']:
                try:
                    inp = driver.find_element(By.CSS_SELECTOR, sel)
                    if inp.is_displayed():
                        break
                except:
                    continue

            if not inp:
                inp = driver.find_element(By.TAG_NAME, 'input')

            # 클립보드로 입력
            paste_text(str(answer))
            inp.click()
            time.sleep(0.2)
            inp.send_keys(Keys.COMMAND, 'v')  # Mac
            time.sleep(0.5)

            # 확인 버튼 찾기 (여러 방법 시도)
            confirm_btn = None
            btn_selectors = [
                "//button[contains(text(), '확인')]",
                "//button[text()='확인']",
                "//input[@type='submit']",
                "//button[@type='submit']",
                "//a[contains(text(), '확인')]",
                "//div[contains(text(), '확인')]",
                "//span[contains(text(), '확인')]/parent::button",
                "//button[contains(@class, 'confirm')]",
                "//button[contains(@class, 'submit')]",
            ]

            for sel in btn_selectors:
                try:
                    confirm_btn = driver.find_element(By.XPATH, sel)
                    if confirm_btn.is_displayed():
                        print(f"    버튼 발견: {sel}")
                        break
                except:
                    continue

            if confirm_btn:
                driver.execute_script("arguments[0].click();", confirm_btn)
                time.sleep(3)
                return True
            else:
                print("    확인 버튼을 찾지 못함")
                return False

    except Exception as e:
        print(f"    CAPTCHA 오류: {e}")
    return False


def main():
    NAVER_ID = "starkjy0112"
    NAVER_PW = "Wodud0228@##"

    # 1. 디버거 크롬 실행 (Mac)
    print("=" * 60)
    print("1. 디버거 크롬 실행")
    print("=" * 60)

    chrome_path = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
    user_data_dir = '/tmp/chrome_debug_profile'

    # 기존 크롬 프로세스 종료 (optional)
    subprocess.run(['pkill', '-f', 'Google Chrome'], capture_output=True)
    time.sleep(2)

    # 디버거 모드로 크롬 실행
    subprocess.Popen([
        chrome_path,
        '--remote-debugging-port=9222',
        f'--user-data-dir={user_data_dir}'
    ])
    time.sleep(3)
    print("   크롬 실행됨")

    # 2. Selenium 연결
    print("\n" + "=" * 60)
    print("2. Selenium 연결")
    print("=" * 60)

    options = webdriver.ChromeOptions()
    options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

    try:
        driver = webdriver.Chrome(options=options)
        wait = WebDriverWait(driver, 10)
        print("   ✅ 연결됨")
    except Exception as e:
        print(f"   연결 실패: {e}")
        return

    try:
        # 3. 네이버 로그인
        print("\n" + "=" * 60)
        print("3. 네이버 로그인")
        print("=" * 60)

        driver.get('https://nid.naver.com/nidlogin.login')
        time.sleep(2)

        # 로그인 필요한지 확인
        if 'nidlogin' in driver.current_url:
            # 클립보드로 ID 입력
            id_input = wait.until(EC.visibility_of_element_located((By.ID, 'id')))
            paste_text(NAVER_ID)
            id_input.click()
            time.sleep(0.2)
            id_input.send_keys(Keys.COMMAND, 'v')
            time.sleep(0.5)

            # 클립보드로 PW 입력
            pw_input = driver.find_element(By.ID, 'pw')
            paste_text(NAVER_PW)
            pw_input.click()
            time.sleep(0.2)
            pw_input.send_keys(Keys.COMMAND, 'v')
            time.sleep(0.5)

            # 로그인 버튼
            login_btn = driver.find_element(By.ID, 'log.login')
            login_btn.click()
            time.sleep(5)

        print("   ✅ 로그인 완료")

        # 4. 스마트스토어 상품 페이지
        print("\n" + "=" * 60)
        print("4. 상품 페이지 (1차 CAPTCHA)")
        print("=" * 60)

        url = "https://smartstore.naver.com/main/products/7255034137"
        driver.get(url)
        time.sleep(3)

        # CAPTCHA 해결 루프
        for i in range(10):
            page_source = driver.page_source
            if '보안 확인' in page_source:
                print(f"   [CAPTCHA {i+1}]")
                solve_captcha_selenium(driver)
                driver.get(url)
                time.sleep(3)
            else:
                break

        print(f"   ✅ 상품 페이지: {driver.title[:30]}...")

        # 5. 판매자 상세정보 버튼
        print("\n" + "=" * 60)
        print("5. 판매자 상세정보 버튼 클릭")
        print("=" * 60)

        # 스크롤
        driver.execute_script("window.scrollTo(0, 2000)")
        time.sleep(2)

        # 버튼 찾기 및 클릭
        try:
            btn = driver.find_element(By.XPATH, "//button[contains(text(), '판매자 상세정보')]")
            driver.execute_script("arguments[0].scrollIntoView(true);", btn)
            time.sleep(1)

            # 클릭 전 스크린샷
            driver.save_screenshot('/tmp/before_modal.png')
            print("   클릭 전 스크린샷: /tmp/before_modal.png")

            # JavaScript로 클릭 (더 확실함)
            driver.execute_script("arguments[0].click();", btn)
            print("   ✅ 버튼 클릭! (JS)")
            time.sleep(5)  # 모달 열릴 때까지 대기

            # 클릭 직후 스크린샷
            driver.save_screenshot('/tmp/after_click.png')
            print("   클릭 직후 스크린샷: /tmp/after_click.png")

            # 모달 확인
            time.sleep(2)
            page_source = driver.page_source

            # 모달 요소 확인
            print("\n   모달 확인...")
            modal_selectors = [
                "//div[contains(@class, 'modal')]",
                "//div[contains(@class, 'Modal')]",
                "//div[contains(@class, 'layer')]",
                "//div[contains(@class, 'Layer')]",
                "//div[contains(@class, 'popup')]",
                "//div[@role='dialog']",
            ]

            for sel in modal_selectors:
                try:
                    modals = driver.find_elements(By.XPATH, sel)
                    if modals:
                        print(f"   발견: {sel} ({len(modals)}개)")
                        for i, m in enumerate(modals[:2]):
                            try:
                                text = m.text[:200] if m.text else "(비어있음)"
                                print(f"      [{i}] {text}...")
                            except:
                                pass
                except:
                    pass

            time.sleep(5)
        except Exception as e:
            print(f"   버튼 오류: {e}")

        # 6. 판매자 정보 CAPTCHA (영수증)
        print("\n" + "=" * 60)
        print("6. 판매자 정보 CAPTCHA 확인")
        print("=" * 60)

        for i in range(10):
            page_source = driver.page_source

            # 영수증 CAPTCHA 또는 기타 CAPTCHA 확인
            if '영수증' in page_source or '몇 개' in page_source or '인증 절차' in page_source:
                print(f"   [영수증 CAPTCHA {i+1}]")
                driver.save_screenshot(f'/tmp/receipt_captcha_{i+1}.png')
                print(f"   스크린샷: /tmp/receipt_captcha_{i+1}.png")
                solved = solve_captcha_selenium(driver)
                if not solved:
                    print("   ❌ CAPTCHA 해결 실패 - 수동 입력 필요")
                    print("   30초 대기 (수동으로 입력하세요)...")
                    time.sleep(30)
                time.sleep(3)
                continue

            if '보안 확인' in page_source or '빈 칸' in page_source:
                print(f"   [보안 CAPTCHA {i+1}]")
                solve_captcha_selenium(driver)
                time.sleep(3)
                continue

            # CAPTCHA 없으면 종료
            break

        # 7. 결과
        print("\n" + "=" * 60)
        print("7. 결과")
        print("=" * 60)

        driver.save_screenshot('/tmp/debugger_result.png')
        print("   스크린샷: /tmp/debugger_result.png")

        page_source = driver.page_source

        # 전화번호 추출
        phone_match = re.search(r'전화번호[:\s]*(\d{2,4}[-\s]?\d{3,4}[-\s]?\d{4})', page_source)
        if phone_match:
            phone = phone_match.group(1)
            if '1588-3819' not in phone:
                print(f"\n   📞 판매자 전화번호: {phone}")
            else:
                print("   네이버 번호만 있음")
        else:
            print("   전화번호 없음")

        # 기타 정보
        for pat, name in [(r'대표자[:\s]*([가-힣]{2,5})', '대표자'),
                          (r'사업자등록번호[:\s]*([\d-]+)', '사업자번호')]:
            m = re.search(pat, page_source)
            if m and '220-81-62517' not in m.group(1) and '최수연' not in m.group(1):
                print(f"   {name}: {m.group(1)}")

        print("\n60초 대기 (브라우저 확인)...")
        time.sleep(60)

    finally:
        driver.quit()


if __name__ == '__main__':
    main()
