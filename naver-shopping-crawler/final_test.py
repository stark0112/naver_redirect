"""
판매자 상세정보 버튼 클릭 후 CAPTCHA 해결 → 전화번호 추출
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
    """CAPTCHA 해결"""
    try:
        # CAPTCHA 페이지인지 확인
        content = await page.content()
        if '보안 확인' not in content and '빈 칸' not in content and '번째' not in content:
            return False

        q = await page.query_selector('text=/빈 칸|번째/')
        if not q:
            return False

        qt = await q.inner_text()
        print(f"      질문: {qt[:40]}...")

        img = await page.query_selector('img')
        if not img:
            return False

        await img.screenshot(path='/tmp/cap.png')
        ocr = get_reader().readtext('/tmp/cap.png')
        text = ' '.join([r[1] for r in ocr])
        print(f"      OCR: {text[:40]}...")

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
            print(f"      답: {answer}")
            inp = await page.query_selector('input')
            btn = await page.query_selector('button:has-text("확인")')
            if inp and btn:
                await inp.fill(str(answer))
                await asyncio.sleep(0.3)
                await btn.click()
                await asyncio.sleep(3)
                return True

    except Exception as e:
        print(f"      오류: {e}")
    return False


async def main():
    NAVER_ID = "starkjy0112"
    NAVER_PW = "Wodud0228@##"

    pw = await async_playwright().start()
    browser = await pw.chromium.launch_persistent_context(
        user_data_dir='/tmp/naver_final',
        headless=False,
        locale='ko-KR',
        viewport={'width': 1280, 'height': 900}
    )

    try:
        page = browser.pages[0] if browser.pages else await browser.new_page()

        # ===== 1. 로그인 =====
        print("=" * 60)
        print("1. 네이버 로그인")
        print("=" * 60)

        await page.goto('https://nid.naver.com/nidlogin.login')
        await asyncio.sleep(2)

        # 이미 로그인 상태면 스킵
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

        print("   ✅ 로그인 완료")

        # ===== 2. 상품 페이지 + 1차 CAPTCHA =====
        print("\n" + "=" * 60)
        print("2. 상품 페이지 (1차 CAPTCHA)")
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
                print(f"   [CAPTCHA {i+1}]")
                await solve_captcha(page)
                continue

            title = await page.title()
            if title and '운영' not in title:
                print(f"   ✅ 상품 페이지: {title[:30]}...")
                break

        # ===== 3. 판매자정보 탭 + 버튼 클릭 =====
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
                await asyncio.sleep(1)
        except:
            pass

        await page.evaluate('window.scrollTo(0, 2000)')
        await asyncio.sleep(1)

        # 버튼 클릭
        try:
            btn = page.locator('button:has-text("판매자 상세정보")').first
            await btn.scroll_into_view_if_needed()
            await asyncio.sleep(0.5)
            await btn.click()
            print("   ✅ 버튼 클릭!")
        except Exception as e:
            print(f"   버튼 오류: {e}")

        await asyncio.sleep(3)

        # ===== 4. 버튼 클릭 후 2차 CAPTCHA =====
        print("\n" + "=" * 60)
        print("4. 2차 CAPTCHA 해결")
        print("=" * 60)

        for i in range(15):
            await asyncio.sleep(2)
            content = await page.content()

            # CAPTCHA 확인
            if '보안 확인' in content or '빈 칸' in content:
                print(f"   [2차 CAPTCHA {i+1}]")
                solved = await solve_captcha(page)
                if not solved:
                    await asyncio.sleep(5)
                continue

            # 판매자 모달 확인 (실제 판매자 정보가 있는지)
            # 네이버 고객센터 번호가 아닌 다른 전화번호가 있으면 성공
            phone_match = re.search(r'전화번호[:\s]*(\d{2,4}[-\s]?\d{3,4}[-\s]?\d{4})', content)
            if phone_match:
                phone = phone_match.group(1)
                if '1588-3819' not in phone and '1588-3816' not in phone:
                    print(f"\n   📞 판매자 전화번호 발견: {phone}")
                    break

            # 대표자 + 사업자번호가 네이버 것이 아니면 성공
            if '대표자' in content:
                rep_match = re.search(r'대표자[:\s]*([가-힣]{2,5})', content)
                biz_match = re.search(r'사업자등록번호[:\s]*([\d-]+)', content)
                if rep_match and biz_match:
                    if '220-81-62517' not in biz_match.group(1):  # 네이버 사업자번호 아님
                        print("   ✅ 판매자 정보 모달 열림!")
                        break

            if i >= 10:
                print("   시간 초과")
                break

        # ===== 5. 결과 추출 =====
        print("\n" + "=" * 60)
        print("5. 결과")
        print("=" * 60)

        await page.screenshot(path='/tmp/seller_modal.png')
        print("   스크린샷: /tmp/seller_modal.png")

        content = await page.content()

        # 전화번호
        phone_found = None
        for pat in [r'전화번호[:\s]*(\d{2,4}[-\s]?\d{3,4}[-\s]?\d{4})',
                    r'전화[:\s]*(\d{2,4}[-\s]?\d{3,4}[-\s]?\d{4})']:
            matches = re.findall(pat, content)
            for m in matches:
                if '1588-3819' not in m and '1588-3816' not in m:
                    phone_found = m
                    break
            if phone_found:
                break

        if phone_found:
            print(f"\n   📞 판매자 전화번호: {phone_found}")
        else:
            print("   ❌ 전화번호를 찾지 못했습니다.")

        # 기타 정보
        info_found = []
        for pat, name in [
            (r'대표자[:\s]*([가-힣]{2,5})', '대표자'),
            (r'상호[명:\s]*([가-힣a-zA-Z0-9\s]+?)[\s<\n]', '상호명'),
            (r'사업자등록번호[:\s]*([\d-]+)', '사업자번호'),
        ]:
            m = re.search(pat, content)
            if m:
                val = m.group(1).strip()
                if '220-81-62517' not in val and '최수연' not in val:  # 네이버 정보 제외
                    info_found.append(f"{name}: {val}")

        for info in info_found:
            print(f"   {info}")

        print("\n브라우저에서 결과를 확인하세요. 60초 대기...")
        await asyncio.sleep(60)

    finally:
        await browser.close()
        await pw.stop()

if __name__ == '__main__':
    asyncio.run(main())
