"""
undetected-chromedriver로 네이버 스마트스토어 크롤링
"""
import undetected_chromedriver as uc
import time
import re
import easyocr

# OCR
reader = None
def get_reader():
    global reader
    if reader is None:
        print("OCR 초기화...")
        reader = easyocr.Reader(['ko', 'en'], gpu=False)
    return reader


def solve_captcha(driver):
    """CAPTCHA 해결"""
    try:
        page_source = driver.page_source

        # 질문 찾기
        q_match = re.search(r'(전화번호[^?]+\?|빈 칸[^?]+\?|몇 개[^?]+\?|영수증[^?]+\?)', page_source)
        if not q_match:
            return False

        question = q_match.group(1)
        print(f"    질문: {question[:50]}...")

        # 이미지 스크린샷
        img = driver.find_element("tag name", "img")
        img.screenshot('/tmp/captcha_uc.png')

        # OCR
        ocr = get_reader().readtext('/tmp/captcha_uc.png')
        text = ' '.join([r[1] for r in ocr])
        print(f"    OCR: {text[:60]}...")

        answer = None

        # 전화번호 문제
        if '전화번호' in question:
            direction = '앞' if '앞에서' in question else '뒤'
            pos_match = re.search(r'(\d+)번째', question)
            pos = int(pos_match.group(1)) if pos_match else 1

            phone_match = re.search(r'(\d{3,4})[-\s](\d{4})', text)
            if phone_match:
                digits = phone_match.group(1) + phone_match.group(2)
                answer = digits[pos - 1] if direction == '앞' else digits[-pos]
                print(f"    전화번호: {digits}, {direction}에서 {pos}번째 = {answer}")

        # 주소 빈칸 문제
        elif '빈 칸' in question or '길' in question:
            addr_match = re.search(r'길\s*(\d+)', text)
            if addr_match:
                answer = addr_match.group(1)
                print(f"    주소 숫자: {answer}")

        # 총 몇 개 문제
        elif '몇 개' in question:
            numbers = re.findall(r'\b(\d{1,2})\b', text)
            quantities = [int(n) for n in numbers if 1 <= int(n) <= 50]
            if quantities:
                answer = sum(quantities[:5])
                print(f"    수량: {quantities[:5]} → {answer}")

        if answer:
            # 입력
            inp = driver.find_element("tag name", "input")
            inp.clear()
            inp.send_keys(str(answer))
            time.sleep(0.5)

            # 확인 버튼 클릭
            buttons = driver.find_elements("tag name", "button")
            for btn in buttons:
                if '확인' in btn.text:
                    btn.click()
                    time.sleep(3)
                    return True

            # 버튼 못 찾으면 Enter
            inp.send_keys("\n")
            time.sleep(3)
            return True

    except Exception as e:
        print(f"    오류: {e}")
    return False


def main():
    NAVER_ID = "starkjy0112"
    NAVER_PW = "Wodud0228@##"

    print("=" * 60)
    print("undetected-chromedriver 테스트")
    print("=" * 60)

    # 브라우저 시작
    options = uc.ChromeOptions()
    options.add_argument("--lang=ko-KR")

    driver = uc.Chrome(options=options, headless=False)

    try:
        # 1. 로그인
        print("\n1. 네이버 로그인...")
        driver.get('https://nid.naver.com/nidlogin.login')
        time.sleep(2)

        if 'nidlogin' in driver.current_url:
            # ID/PW 입력
            id_input = driver.find_element("id", "id")
            id_input.send_keys(NAVER_ID)
            time.sleep(0.5)

            pw_input = driver.find_element("id", "pw")
            pw_input.send_keys(NAVER_PW)
            time.sleep(0.5)

            # 로그인 버튼
            login_btn = driver.find_element("id", "log.login")
            login_btn.click()
            time.sleep(5)

        print("   로그인 완료")

        # 2. 상품 페이지
        print("\n2. 상품 페이지...")
        url = "https://smartstore.naver.com/main/products/7255034137"

        for i in range(10):
            driver.get(url)
            time.sleep(3)

            page_source = driver.page_source
            if '보안 확인' in page_source or '전화번호' in page_source:
                print(f"   CAPTCHA {i+1}")
                driver.save_screenshot(f'/tmp/uc_captcha_{i+1}.png')
                solve_captcha(driver)
                continue

            if driver.title and '운영' not in driver.title:
                print(f"   완료: {driver.title[:30]}...")
                break

        # 3. 판매자 상세정보 버튼
        print("\n3. 판매자 상세정보 버튼...")
        driver.execute_script("window.scrollTo(0, 2000)")
        time.sleep(2)

        try:
            buttons = driver.find_elements("tag name", "button")
            for btn in buttons:
                if '판매자 상세정보' in btn.text:
                    driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                    time.sleep(1)
                    btn.click()
                    print("   버튼 클릭!")
                    break
        except Exception as e:
            print(f"   버튼 오류: {e}")

        time.sleep(5)

        # 4. CAPTCHA 해결
        print("\n4. CAPTCHA 확인...")
        for i in range(10):
            page_source = driver.page_source

            if '영수증' in page_source or '인증 절차' in page_source or '전화번호' in page_source:
                print(f"   CAPTCHA {i+1}")
                driver.save_screenshot(f'/tmp/uc_seller_captcha_{i+1}.png')
                solved = solve_captcha(driver)
                if not solved:
                    print("   수동 입력 필요 (30초 대기)...")
                    time.sleep(30)
                continue

            break

        # 5. 결과
        print("\n5. 결과...")
        driver.save_screenshot('/tmp/uc_result.png')
        print("   스크린샷: /tmp/uc_result.png")

        page_source = driver.page_source

        # 전화번호 추출
        phone_match = re.search(r'전화번호[:\s]*(0\d{1,2}[-\s]?\d{3,4}[-\s]?\d{4})', page_source)
        if phone_match:
            phone = phone_match.group(1)
            if '1588' not in phone:
                print(f"\n   📞 판매자 전화번호: {phone}")

        print("\n60초 대기 (브라우저 확인)...")
        time.sleep(60)

    finally:
        driver.quit()


if __name__ == '__main__':
    main()
