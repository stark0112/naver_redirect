"""
네이버 자동 로그인 + 전화번호 추출 테스트
"""
import asyncio
import re
import easyocr
from patchright.async_api import async_playwright

reader = None

def get_reader():
    global reader
    if reader is None:
        reader = easyocr.Reader(['ko', 'en'], gpu=False)
    return reader

async def solve_captcha(page):
    try:
        q = await page.query_selector('text=/빈 칸|번째/')
        if not q:
            return False

        qt = await q.inner_text()
        img = await page.query_selector('img')
        if not img:
            return False

        await img.screenshot(path='/tmp/cap.png')
        ocr = get_reader().readtext('/tmp/cap.png')
        text = ' '.join([r[1] for r in ocr])

        answer = None
        if '전화번호' in qt:
            d = '앞' if '앞에서' in qt else '뒤'
            p = int(re.search(r'(\d+)번째', qt).group(1)) if re.search(r'(\d+)번째', qt) else 1
            m = re.search(r'(\d{3,4})[-\s](\d{4})', text)
            if m:
                nums = m.group(1) + m.group(2)
                answer = nums[p-1] if d == '앞' else nums[-p]
        elif '길' in qt:
            m = re.search(r'길\s*(\d+)', text)
            if m:
                answer = m.group(1)

        if answer:
            inp = await page.query_selector('input')
            btn = await page.query_selector('button:has-text("확인")')
            if inp and btn:
                await inp.fill(str(answer))
                await asyncio.sleep(0.3)
                await btn.click()
                await asyncio.sleep(2)
                return True
    except:
        pass
    return False


async def main():
    # 로그인 정보
    NAVER_ID = "starkjy0112"
    NAVER_PW = "Wodud0228@##"

    pw = await async_playwright().start()
    browser = await pw.chromium.launch_persistent_context(
        user_data_dir='/tmp/naver_auto_login',
        headless=False,
        locale='ko-KR',
        viewport={'width': 1280, 'height': 900}
    )

    try:
        page = browser.pages[0] if browser.pages else await browser.new_page()

        # 1. 네이버 로그인
        print("=" * 60)
        print("1. 네이버 로그인...")
        print("=" * 60)

        await page.goto('https://nid.naver.com/nidlogin.login')
        await asyncio.sleep(2)

        # 로그인 폼 입력
        try:
            # ID 입력
            id_input = page.locator('#id')
            await id_input.click()
            await asyncio.sleep(0.3)
            await id_input.fill(NAVER_ID)
            await asyncio.sleep(0.5)

            # PW 입력
            pw_input = page.locator('#pw')
            await pw_input.click()
            await asyncio.sleep(0.3)
            await pw_input.fill(NAVER_PW)
            await asyncio.sleep(0.5)

            # 로그인 버튼 클릭
            login_btn = page.locator('#log\\.login')
            await login_btn.click()
            print("   로그인 버튼 클릭...")

            await asyncio.sleep(5)

        except Exception as e:
            print(f"   로그인 폼 입력 오류: {e}")

        # 로그인 성공 확인
        current_url = page.url
        if 'nidlogin' not in current_url:
            print("   ✅ 로그인 성공!")
        else:
            print("   ⚠️ 추가 인증이 필요할 수 있습니다.")
            print("   브라우저에서 직접 인증을 완료해주세요.")
            print("   30초 대기...")
            await asyncio.sleep(30)

        # 2. 스마트스토어 상품 페이지
        print("\n" + "=" * 60)
        print("2. 스마트스토어 상품 페이지...")
        print("=" * 60)

        url = "https://smartstore.naver.com/main/products/7255034137"
        print(f"   URL: {url}")

        for attempt in range(10):
            try:
                await page.goto(url, wait_until='domcontentloaded', timeout=15000)
            except:
                pass
            await asyncio.sleep(2)

            content = await page.content()
            if '보안 확인' in content:
                print(f"   CAPTCHA 해결 중... ({attempt+1}/10)")
                await solve_captcha(page)
            elif '운영이 중지' not in content:
                print("   ✅ 상품 페이지 접속!")
                break

        title = await page.title()
        print(f"   제목: {title[:40] if title else 'N/A'}...")

        # 3. 판매자정보 탭
        print("\n" + "=" * 60)
        print("3. 판매자 정보 추출...")
        print("=" * 60)

        await page.evaluate('window.scrollTo(0, 1500)')
        await asyncio.sleep(1)

        # 판매자정보 탭 클릭
        try:
            tab = page.locator('text=판매자정보').first
            if await tab.is_visible(timeout=2000):
                await tab.click()
                await asyncio.sleep(2)
                print("   ✅ 판매자정보 탭 클릭")
        except:
            pass

        # 판매자 상세정보 버튼 클릭
        await page.evaluate('window.scrollTo(0, 2000)')
        await asyncio.sleep(1)

        try:
            btn = page.locator('button:has-text("판매자 상세정보 확인")').first
            if await btn.is_visible(timeout=2000):
                await btn.scroll_into_view_if_needed()
                await btn.click()
                print("   ✅ 판매자 상세정보 버튼 클릭")
                await asyncio.sleep(3)
        except:
            pass

        await page.screenshot(path='/tmp/result.png')

        # 4. 전화번호 추출
        print("\n" + "=" * 60)
        print("4. 결과")
        print("=" * 60)

        content = await page.content()

        # 로그인 필요 확인
        if '로그인이 필요' in content:
            print("   ⚠️ 로그인이 필요합니다!")
            print("   브라우저에서 로그인 상태를 확인해주세요.")
        else:
            # 전화번호 추출
            phone_patterns = [
                r'전화번호[:\s]*(\d{2,4}[-\s]?\d{3,4}[-\s]?\d{4})',
                r'대표전화[:\s]*(\d{2,4}[-\s]?\d{3,4}[-\s]?\d{4})',
            ]

            phone_found = None
            for pat in phone_patterns:
                match = re.search(pat, content)
                if match:
                    phone = match.group(1)
                    if '1588-3819' not in phone and '1588-3816' not in phone:
                        phone_found = phone
                        break

            if phone_found:
                print(f"\n   📞 판매자 전화번호: {phone_found}")
            else:
                print("   전화번호를 찾지 못했습니다.")

            # 판매자 정보
            for kw in ['대표자', '상호명', '사업자등록번호']:
                m = re.search(f'{kw}[:\\s]*([^<\\n]+)', content)
                if m:
                    print(f"   {kw}: {m.group(1)[:30]}")

        print("\n스크린샷: /tmp/result.png")
        print("\n30초 대기 (브라우저 확인)...")
        await asyncio.sleep(30)

    finally:
        await browser.close()
        await pw.stop()

if __name__ == '__main__':
    asyncio.run(main())
