"""
완전한 전화번호 추출 (버튼 클릭 후 CAPTCHA 포함)
"""
import asyncio
import re
import easyocr
from patchright.async_api import async_playwright

reader = None
def get_reader():
    global reader
    if reader is None:
        print("OCR 초기화...")
        reader = easyocr.Reader(['ko', 'en'], gpu=False)
    return reader


async def solve_captcha(page):
    """CAPTCHA 자동 해결"""
    try:
        q = await page.query_selector('text=/빈 칸|번째/')
        if not q:
            return False

        qt = await q.inner_text()
        print(f"    질문: {qt[:50]}...")

        img = await page.query_selector('img')
        if not img:
            return False

        await img.screenshot(path='/tmp/cap.png')
        ocr = get_reader().readtext('/tmp/cap.png')
        text = ' '.join([r[1] for r in ocr])
        print(f"    OCR: {text[:50]}...")

        answer = None

        if '전화번호' in qt:
            d = '앞' if '앞에서' in qt else '뒤'
            p = int(re.search(r'(\d+)번째', qt).group(1)) if re.search(r'(\d+)번째', qt) else 1
            m = re.search(r'(\d{3,4})[-\s](\d{4})', text)
            if m:
                nums = m.group(1) + m.group(2)
                answer = nums[p-1] if d == '앞' else nums[-p]
                print(f"    전화: {nums}, {d}에서 {p}번째 = {answer}")

        elif '길' in qt:
            m = re.search(r'길\s*(\d+)', text)
            if m:
                answer = m.group(1)
                print(f"    주소: {answer}")

        if answer:
            inp = await page.query_selector('input')
            btn = await page.query_selector('button:has-text("확인")')
            if inp and btn:
                await inp.fill(str(answer))
                await asyncio.sleep(0.3)
                await btn.click()
                await asyncio.sleep(3)
                return True

    except Exception as e:
        print(f"    오류: {e}")
    return False


async def main():
    NAVER_ID = "starkjy0112"
    NAVER_PW = "Wodud0228@##"

    pw = await async_playwright().start()
    browser = await pw.chromium.launch_persistent_context(
        user_data_dir='/tmp/naver_test_final',
        headless=False,
        locale='ko-KR',
        viewport={'width': 1280, 'height': 900}
    )

    try:
        page = browser.pages[0] if browser.pages else await browser.new_page()

        # 1. 로그인
        print("=" * 60)
        print("1. 네이버 로그인")
        print("=" * 60)

        await page.goto('https://www.naver.com')
        await asyncio.sleep(2)

        cookies = await browser.cookies()
        logged_in = any('NID_AUT' in c.get('name', '') for c in cookies)

        if not logged_in:
            print("   로그인 중...")
            await page.goto('https://nid.naver.com/nidlogin.login')
            await asyncio.sleep(2)
            await page.locator('#id').fill(NAVER_ID)
            await asyncio.sleep(0.5)
            await page.locator('#pw').fill(NAVER_PW)
            await asyncio.sleep(0.5)
            await page.locator('#log\\.login').click()
            await asyncio.sleep(5)

            if 'nidlogin' in page.url:
                print("   추가 인증 필요. 30초 대기...")
                await asyncio.sleep(30)

        print("   ✅ 로그인 완료!")

        # 2. 상품 페이지 (1차 CAPTCHA)
        print("\n" + "=" * 60)
        print("2. 상품 페이지 접속")
        print("=" * 60)

        url = "https://smartstore.naver.com/main/products/7255034137"

        for i in range(15):
            try:
                await page.goto(url, wait_until='domcontentloaded', timeout=15000)
            except:
                pass
            await asyncio.sleep(2)

            content = await page.content()
            if '보안 확인' in content:
                print(f"   [1차 CAPTCHA {i+1}]")
                await solve_captcha(page)
            elif '운영이 중지' not in content:
                break

        title = await page.title()
        print(f"   ✅ 접속: {title[:30] if title else 'N/A'}...")

        # 3. 판매자정보 탭
        print("\n" + "=" * 60)
        print("3. 판매자 상세정보 버튼 클릭")
        print("=" * 60)

        await page.evaluate('window.scrollTo(0, 1500)')
        await asyncio.sleep(1)

        # 판매자정보 탭
        try:
            tab = page.locator('text=판매자정보').first
            if await tab.is_visible(timeout=2000):
                await tab.click()
                await asyncio.sleep(2)
        except:
            pass

        await page.evaluate('window.scrollTo(0, 2000)')
        await asyncio.sleep(1)

        # 상세정보 버튼
        try:
            btn = page.locator('button:has-text("판매자 상세정보")').first
            if await btn.is_visible(timeout=2000):
                await btn.click()
                print("   ✅ 버튼 클릭!")
                await asyncio.sleep(3)
        except:
            pass

        # 4. 버튼 클릭 후 CAPTCHA (2차)
        print("\n" + "=" * 60)
        print("4. 버튼 클릭 후 CAPTCHA 해결")
        print("=" * 60)

        for i in range(10):
            content = await page.content()

            # CAPTCHA 확인
            if '보안 확인' in content or '빈 칸' in content:
                print(f"   [2차 CAPTCHA {i+1}]")
                solved = await solve_captcha(page)
                if solved:
                    await asyncio.sleep(2)
                    continue
                else:
                    await asyncio.sleep(5)
                    continue

            # 모달/판매자 정보 확인
            if '전화번호' in content and '대표자' in content:
                print("   ✅ 판매자 정보 표시됨!")
                break

            # 로그인 필요
            if '로그인이 필요' in content:
                print("   ⚠️ 로그인 필요!")
                break

            await asyncio.sleep(2)

        # 5. 결과
        print("\n" + "=" * 60)
        print("5. 결과")
        print("=" * 60)

        await page.screenshot(path='/tmp/final_result.png')
        print("   스크린샷: /tmp/final_result.png")

        content = await page.content()

        # 전화번호 추출
        patterns = [
            r'전화번호[:\s]*(\d{2,4}[-\s]?\d{3,4}[-\s]?\d{4})',
            r'대표전화[:\s]*(\d{2,4}[-\s]?\d{3,4}[-\s]?\d{4})',
        ]

        phone_found = None
        for pat in patterns:
            m = re.search(pat, content)
            if m:
                phone = m.group(1)
                if '1588-3819' not in phone:
                    phone_found = phone
                    break

        if phone_found:
            print(f"\n   📞 판매자 전화번호: {phone_found}")
        else:
            print("   전화번호 못찾음")

        # 기타 정보
        for pat, name in [(r'대표자[:\s]*([가-힣]{2,5})', '대표자'),
                          (r'사업자등록번호[:\s]*([\d-]+)', '사업자번호')]:
            m = re.search(pat, content)
            if m and '220-81-62517' not in m.group(1):
                print(f"   {name}: {m.group(1)}")

        print("\n60초 대기...")
        await asyncio.sleep(60)

    finally:
        await browser.close()
        await pw.stop()

if __name__ == '__main__':
    asyncio.run(main())
