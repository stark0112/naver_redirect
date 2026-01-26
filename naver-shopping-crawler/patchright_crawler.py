"""
Patchright 기반 네이버 스마트스토어 크롤러
- Patchright: CDP 감지 우회 (Runtime.Enable 패치)
- 쿠키 저장/재사용
"""
import json
import os
import re
import time
from patchright.sync_api import sync_playwright

COOKIE_FILE = '/tmp/naver_patchright_cookies.json'


def save_cookies(context):
    """쿠키 저장"""
    cookies = context.cookies()
    with open(COOKIE_FILE, 'w') as f:
        json.dump(cookies, f)
    print(f"   쿠키 저장됨: {len(cookies)}개")


def load_cookies(context):
    """쿠키 로드"""
    if not os.path.exists(COOKIE_FILE):
        return False

    with open(COOKIE_FILE, 'r') as f:
        cookies = json.load(f)

    context.add_cookies(cookies)
    print(f"   쿠키 로드됨: {len(cookies)}개")
    return True


def manual_login():
    """수동 로그인 모드"""
    print("=" * 60)
    print("수동 로그인 모드 (Patchright - CDP 우회)")
    print("=" * 60)
    print("1. 브라우저가 열리면 네이버에 로그인하세요")
    print("2. 로그인 완료 후 터미널에서 Enter를 누르세요")
    print("=" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
            ]
        )

        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='ko-KR',
        )

        page = context.new_page()
        page.goto('https://nid.naver.com/nidlogin.login?mode=form&url=https://www.naver.com/')

        input("\n>>> 로그인 완료 후 Enter 키를 누르세요...")

        # 쿠키 저장
        save_cookies(context)
        print("\n쿠키가 저장되었습니다!")

        browser.close()


def auto_crawl(product_url):
    """자동 크롤링 모드"""
    print("=" * 60)
    print("자동 크롤링 모드 (Patchright - CDP 우회)")
    print("=" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,  # 디버깅용
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
            ]
        )

        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='ko-KR',
        )

        page = context.new_page()

        # 쿠키 로드
        if os.path.exists(COOKIE_FILE):
            load_cookies(context)

        try:
            # 상품 페이지 접근
            print(f"\n상품 페이지 접근: {product_url}")
            page.goto(product_url, wait_until='networkidle')
            time.sleep(3)

            # 페이지 확인
            title = page.title()
            print(f"   페이지 제목: {title}")

            # 차단 체크
            content = page.content()
            if '서비스 접속이 불가' in content or '접근이 차단' in content:
                print("   ⚠️ 접근 차단됨!")
                page.screenshot(path='/tmp/patchright_blocked.png')
                print("   스크린샷: /tmp/patchright_blocked.png")
                browser.close()
                return

            # CAPTCHA 체크
            if '보안 확인' in content:
                print("   ⚠️ 보안 확인 페이지 감지")
                page.screenshot(path='/tmp/patchright_captcha.png')
                print("   스크린샷: /tmp/patchright_captcha.png")
                print("   >>> 30초 대기 (수동으로 CAPTCHA 해결)...")
                time.sleep(30)

            # 스크롤
            page.evaluate('window.scrollTo(0, 2000)')
            time.sleep(2)

            # 판매자 상세정보 버튼 찾기
            print("\n판매자 상세정보 버튼 찾기...")

            # 여러 셀렉터 시도
            selectors = [
                'button:has-text("판매자 상세정보")',
                'text=판매자 상세정보 확인',
                '[class*="seller"] button',
            ]

            btn = None
            for sel in selectors:
                try:
                    btn = page.wait_for_selector(sel, timeout=5000)
                    if btn:
                        print(f"   버튼 발견: {sel}")
                        break
                except:
                    continue

            if btn:
                # 버튼으로 스크롤
                btn.scroll_into_view_if_needed()
                time.sleep(1)

                # 클릭
                btn.click()
                print("   버튼 클릭!")
                time.sleep(5)

                # CAPTCHA 체크
                content = page.content()
                if '영수증' in content or ('전화번호' in content and '번째' in content):
                    print("\n   ⚠️ 판매자 정보 CAPTCHA 발생!")
                    page.screenshot(path='/tmp/patchright_seller_captcha.png')
                    print("   스크린샷: /tmp/patchright_seller_captcha.png")
                    print("   >>> 60초 대기 (수동으로 CAPTCHA 해결)...")
                    time.sleep(60)
            else:
                print("   버튼을 찾지 못함")

            # 결과 추출
            print("\n결과 추출...")
            page.screenshot(path='/tmp/patchright_result.png')
            content = page.content()

            # 전화번호 추출
            phone_patterns = [
                r'전화번호[:\s]*(0\d{1,2}[-\s]?\d{3,4}[-\s]?\d{4})',
                r'연락처[:\s]*(0\d{1,2}[-\s]?\d{3,4}[-\s]?\d{4})',
                r'(0\d{1,2}-\d{3,4}-\d{4})',
            ]

            found_phones = set()
            for pat in phone_patterns:
                matches = re.findall(pat, content)
                for phone in matches:
                    if '1588' not in phone and '1544' not in phone:
                        found_phones.add(phone)

            if found_phones:
                for phone in found_phones:
                    print(f"   📞 전화번호: {phone}")
            else:
                print("   전화번호를 찾지 못했습니다.")

            # 기타 정보
            info_patterns = [
                (r'대표자[:\s]*([가-힣]{2,5})', '대표자'),
                (r'상호[명:\s]*([가-힣a-zA-Z0-9\s]+)', '상호명'),
                (r'사업자등록번호[:\s]*([\d-]+)', '사업자번호'),
            ]

            for pat, name in info_patterns:
                match = re.search(pat, content)
                if match:
                    val = match.group(1).strip()
                    if '220-81-62517' not in val and '최수연' not in val:
                        print(f"   {name}: {val}")

            # 쿠키 갱신
            save_cookies(context)

            print(f"\n스크린샷: /tmp/patchright_result.png")
            print("\n60초 대기 (브라우저 확인)...")
            time.sleep(60)

        except Exception as e:
            print(f"오류: {e}")
            page.screenshot(path='/tmp/patchright_error.png')

        finally:
            browser.close()


def main():
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == 'login':
        manual_login()
    else:
        url = "https://smartstore.naver.com/main/products/7255034137"
        if len(sys.argv) > 1:
            url = sys.argv[1]
        auto_crawl(url)


if __name__ == '__main__':
    main()
