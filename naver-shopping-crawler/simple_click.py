"""
버튼 클릭 후 대기 - 간단 테스트
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
        print(f"    질문: {qt[:40]}...")

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
            print(f"    답: {answer}")
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
        user_data_dir='/tmp/naver_simple',
        headless=False,
        locale='ko-KR',
        viewport={'width': 1280, 'height': 900}
    )

    try:
        page = browser.pages[0] if browser.pages else await browser.new_page()

        # 로그인
        print("1. 로그인...")
        await page.goto('https://nid.naver.com/nidlogin.login')
        await asyncio.sleep(2)
        if 'nidlogin' in page.url:
            await page.locator('#id').fill(NAVER_ID)
            await asyncio.sleep(0.3)
            await page.locator('#pw').fill(NAVER_PW)
            await asyncio.sleep(0.3)
            await page.locator('#log\\.login').click()
            await asyncio.sleep(5)
        print("   완료")

        # 상품 페이지
        print("\n2. 상품 페이지...")
        url = "https://smartstore.naver.com/main/products/7255034137"
        for i in range(10):
            await page.goto(url, wait_until='domcontentloaded', timeout=15000)
            await asyncio.sleep(2)
            content = await page.content()
            if '보안 확인' in content:
                print(f"   CAPTCHA {i+1}")
                await solve_captcha(page)
                continue
            break
        print(f"   완료: {(await page.title())[:30]}...")

        # 판매자정보 섹션으로 스크롤
        print("\n3. 버튼 클릭...")
        await page.evaluate('window.scrollTo(0, 2000)')
        await asyncio.sleep(2)

        # 버튼 클릭
        btn = page.locator('button:has-text("판매자 상세정보 확인")').first
        await btn.scroll_into_view_if_needed()
        await asyncio.sleep(1)
        await btn.click()
        print("   버튼 클릭 완료!")

        # 대기 (CAPTCHA 또는 모달이 나타날 때까지)
        print("\n4. 변화 대기 (10초)...")
        await asyncio.sleep(10)

        # URL 확인
        print(f"   현재 URL: {page.url}")

        # CAPTCHA 또는 판매자 정보 확인
        content = await page.content()

        if '보안 확인' in content or '빈 칸' in content:
            print("\n5. ⚠️ CAPTCHA 발견! 해결 시도...")

            for i in range(10):
                solved = await solve_captcha(page)
                if solved:
                    await asyncio.sleep(3)
                    content = await page.content()
                    if '보안 확인' not in content:
                        print("   CAPTCHA 해결됨!")
                        break
                else:
                    await asyncio.sleep(5)

        # 전화번호 추출
        print("\n6. 결과...")
        content = await page.content()

        phone_match = re.search(r'전화번호[:\s]*(\d{2,4}[-\s]?\d{3,4}[-\s]?\d{4})', content)
        if phone_match:
            phone = phone_match.group(1)
            if '1588-3819' not in phone:
                print(f"   📞 판매자 전화번호: {phone}")
            else:
                print("   네이버 번호만 있음")
        else:
            print("   전화번호 없음")

        print("\n60초 대기 (브라우저 확인)...")
        await asyncio.sleep(60)

    except Exception as e:
        print(f"오류: {e}")

    finally:
        await browser.close()
        await pw.stop()

if __name__ == '__main__':
    asyncio.run(main())
