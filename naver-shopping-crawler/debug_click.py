"""
버튼 클릭 후 변화 상세 디버깅
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
        content = await page.content()
        if '보안 확인' not in content:
            return False

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
                await asyncio.sleep(3)
                return True
    except:
        pass
    return False


async def main():
    NAVER_ID = "starkjy0112"
    NAVER_PW = "Wodud0228@##"

    pw = await async_playwright().start()
    browser = await pw.chromium.launch_persistent_context(
        user_data_dir='/tmp/naver_debug',
        headless=False,
        locale='ko-KR',
        viewport={'width': 1280, 'height': 900}
    )

    try:
        page = browser.pages[0] if browser.pages else await browser.new_page()

        # 로그인
        print("로그인...")
        await page.goto('https://nid.naver.com/nidlogin.login')
        await asyncio.sleep(2)
        if 'nidlogin' in page.url:
            try:
                await page.locator('#id').fill(NAVER_ID)
                await asyncio.sleep(0.3)
                await page.locator('#pw').fill(NAVER_PW)
                await asyncio.sleep(0.3)
                await page.locator('#log\\.login').click()
                await asyncio.sleep(5)
            except:
                pass
        print("로그인 완료")

        # 상품 페이지
        url = "https://smartstore.naver.com/main/products/7255034137"
        for i in range(10):
            try:
                await page.goto(url, wait_until='domcontentloaded', timeout=15000)
            except:
                pass
            await asyncio.sleep(2)
            content = await page.content()
            if '보안 확인' in content:
                print(f"CAPTCHA {i+1}")
                await solve_captcha(page)
                continue
            break

        print(f"페이지: {await page.title()}")

        # 스크롤
        await page.evaluate('window.scrollTo(0, 2000)')
        await asyncio.sleep(2)

        # 버튼 찾기
        print("\n버튼 찾기...")
        all_buttons = await page.locator('button').all()
        for btn in all_buttons:
            try:
                text = await btn.inner_text()
                if '판매자' in text or '상세정보' in text:
                    print(f"  발견: '{text}'")
            except:
                pass

        # 모든 페이지 (팝업) 확인
        print(f"\n현재 페이지 수: {len(browser.pages)}")

        # 버튼 클릭 시도
        print("\n버튼 클릭...")
        btn = page.locator('button:has-text("판매자 상세정보")').first

        # 클릭 전 URL
        url_before = page.url
        print(f"클릭 전 URL: {url_before}")

        try:
            await btn.scroll_into_view_if_needed()
            await asyncio.sleep(1)

            # 스크린샷
            await page.screenshot(path='/tmp/before_click.png')
            print("클릭 전 스크린샷: /tmp/before_click.png")

            # 클릭
            await btn.click()
            print("클릭 완료!")

            await asyncio.sleep(5)

        except Exception as e:
            print(f"클릭 오류: {e}")

        # 클릭 후 상태
        print(f"\n클릭 후 페이지 수: {len(browser.pages)}")
        print(f"클릭 후 URL: {page.url}")

        # 새 팝업/탭 확인
        if len(browser.pages) > 1:
            print("새 탭/팝업 발견!")
            for i, p in enumerate(browser.pages):
                print(f"  [{i}] {p.url}")

        # 스크린샷
        await page.screenshot(path='/tmp/after_click.png')
        print("클릭 후 스크린샷: /tmp/after_click.png")

        # iframe 확인
        frames = page.frames
        print(f"\nframe 수: {len(frames)}")
        for i, f in enumerate(frames):
            print(f"  [{i}] {f.url[:50]}...")

        # 모달/레이어 확인
        print("\n모달 요소 확인...")
        for sel in ['[class*="modal"]', '[class*="Modal"]', '[class*="layer"]', '[class*="Layer"]',
                    '[class*="popup"]', '[class*="Popup"]', '[role="dialog"]']:
            try:
                count = await page.locator(sel).count()
                if count > 0:
                    print(f"  {sel}: {count}개")
                    for i in range(min(count, 3)):
                        elem = page.locator(sel).nth(i)
                        vis = await elem.is_visible()
                        if vis:
                            text = await elem.inner_text()
                            print(f"    [{i}] visible: {text[:100]}...")
            except:
                pass

        # CAPTCHA 확인
        content = await page.content()
        if '보안 확인' in content or '빈 칸' in content:
            print("\n⚠️ CAPTCHA 발견!")
            await page.screenshot(path='/tmp/captcha_after.png')

        print("\n60초 대기 (브라우저 확인)...")
        await asyncio.sleep(60)

    finally:
        await browser.close()
        await pw.stop()

if __name__ == '__main__':
    asyncio.run(main())
