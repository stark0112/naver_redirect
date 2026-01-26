"""
판매자 정보 영역 디버깅
"""
import asyncio
import re
from patchright.async_api import async_playwright

async def main():
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

        # 로그인 확인
        await page.goto('https://www.naver.com')
        await asyncio.sleep(2)

        cookies = await browser.cookies()
        logged_in = any('NID' in c.get('name', '') for c in cookies)

        if not logged_in:
            print("로그인 중...")
            await page.goto('https://nid.naver.com/nidlogin.login')
            await asyncio.sleep(1)

            await page.locator('#id').fill(NAVER_ID)
            await asyncio.sleep(0.3)
            await page.locator('#pw').fill(NAVER_PW)
            await asyncio.sleep(0.3)
            await page.locator('#log\\.login').click()
            await asyncio.sleep(5)

        print("로그인 완료!")

        # 상품 페이지
        url = "https://smartstore.naver.com/main/products/7255034137"
        await page.goto(url, wait_until='domcontentloaded')
        await asyncio.sleep(3)

        print(f"페이지: {await page.title()}")

        # 하단으로 스크롤
        await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        await asyncio.sleep(2)

        # 판매자정보 탭 찾기
        print("\n=== 판매자정보 탭 찾기 ===")
        all_links = await page.locator('a, button').all()
        for link in all_links:
            try:
                text = await link.inner_text()
                if '판매자' in text:
                    print(f"발견: '{text}'")
                    href = await link.get_attribute('href')
                    if href:
                        print(f"  href: {href}")
            except:
                pass

        # 판매자정보 링크 클릭
        seller_link = page.locator('a:has-text("판매자 정보")').first
        try:
            if await seller_link.is_visible(timeout=2000):
                await seller_link.click()
                print("\n'판매자 정보' 링크 클릭!")
                await asyncio.sleep(2)
        except:
            pass

        # 페이지 스크롤 (판매자정보 섹션)
        await page.evaluate('window.scrollTo(0, 1800)')
        await asyncio.sleep(1)

        await page.screenshot(path='/tmp/debug1.png')
        print("스크린샷1: /tmp/debug1.png")

        # 판매자 상세정보 확인 버튼 찾기
        print("\n=== 판매자 상세정보 버튼 찾기 ===")
        buttons = await page.locator('button').all()
        for btn in buttons:
            try:
                text = await btn.inner_text()
                if '상세정보' in text or '판매자' in text:
                    print(f"버튼 발견: '{text}'")
                    visible = await btn.is_visible()
                    print(f"  visible: {visible}")
            except:
                pass

        # 버튼 클릭
        detail_btn = page.locator('button:has-text("판매자 상세정보")').first
        try:
            await detail_btn.scroll_into_view_if_needed()
            await asyncio.sleep(0.5)
            print("\n버튼 클릭 시도...")
            await detail_btn.click()
            await asyncio.sleep(3)
            print("버튼 클릭 완료!")
        except Exception as e:
            print(f"버튼 클릭 실패: {e}")

        await page.screenshot(path='/tmp/debug2.png')
        print("스크린샷2: /tmp/debug2.png")

        # 페이지 변화 확인
        print("\n=== 모달/레이어 확인 ===")
        selectors = [
            '[class*="modal"]',
            '[class*="Modal"]',
            '[class*="layer"]',
            '[class*="Layer"]',
            '[class*="popup"]',
            '[class*="Popup"]',
            '[role="dialog"]',
            '[class*="seller"]',
            '[class*="Seller"]',
        ]

        for sel in selectors:
            try:
                elems = page.locator(sel)
                count = await elems.count()
                if count > 0:
                    print(f"\n{sel}: {count}개")
                    for i in range(min(count, 3)):
                        elem = elems.nth(i)
                        visible = await elem.is_visible()
                        if visible:
                            text = await elem.inner_text()
                            print(f"  [{i}] visible, 내용: {text[:100]}...")
            except:
                pass

        # 전체 페이지에서 판매자 정보 추출
        print("\n=== 페이지에서 판매자 정보 찾기 ===")
        content = await page.content()

        # 로그인 필요 메시지
        if '로그인이 필요' in content or '로그인 후' in content:
            print("⚠️ 로그인이 필요한 서비스입니다!")

        # 전화번호 패턴
        patterns = [
            (r'전화번호[:\s]*(\d{2,4}[-\s]?\d{3,4}[-\s]?\d{4})', '전화번호'),
            (r'연락처[:\s]*(\d{2,4}[-\s]?\d{3,4}[-\s]?\d{4})', '연락처'),
            (r'대표자[:\s]*([가-힣]{2,5})', '대표자'),
            (r'상호[명:\s]*([가-힣a-zA-Z0-9\s]+?)[\s<]', '상호명'),
        ]

        for pat, name in patterns:
            matches = re.findall(pat, content)
            if matches:
                # 네이버 번호 제외
                for m in matches:
                    if '1588-3819' not in str(m) and '1588-3816' not in str(m):
                        print(f"{name}: {m}")

        print("\n60초 대기 (브라우저에서 직접 확인)...")
        await asyncio.sleep(60)

    finally:
        await browser.close()
        await pw.stop()

if __name__ == '__main__':
    asyncio.run(main())
