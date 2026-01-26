"""
완전한 전화번호 추출 테스트 (로그인 + CAPTCHA + 판매자정보)
"""
import asyncio
import re
import easyocr
from patchright.async_api import async_playwright

# OCR 리더
reader = None
def get_reader():
    global reader
    if reader is None:
        print("OCR 초기화 중...")
        reader = easyocr.Reader(['ko', 'en'], gpu=False)
    return reader


async def solve_captcha(page):
    """CAPTCHA 자동 해결"""
    try:
        q = await page.query_selector('text=/빈 칸|번째/')
        if not q:
            return False

        qt = await q.inner_text()
        print(f"  📝 질문: {qt[:50]}...")

        img = await page.query_selector('img')
        if not img:
            return False

        await img.screenshot(path='/tmp/cap.png')
        ocr = get_reader().readtext('/tmp/cap.png')
        text = ' '.join([r[1] for r in ocr])
        print(f"  📖 OCR: {text[:60]}...")

        answer = None

        # 전화번호 문제
        if '전화번호' in qt:
            direction = '앞' if '앞에서' in qt else '뒤'
            pos_match = re.search(r'(\d+)번째', qt)
            pos = int(pos_match.group(1)) if pos_match else 1

            # 전화번호 찾기
            phone_match = re.search(r'(\d{3,4})[-\s](\d{4})', text)
            if phone_match:
                digits = phone_match.group(1) + phone_match.group(2)
                if direction == '앞':
                    answer = digits[pos - 1] if pos <= len(digits) else None
                else:
                    answer = digits[-pos] if pos <= len(digits) else None
                print(f"  📞 전화번호: {digits}, {direction}에서 {pos}번째 = {answer}")

        # 주소 문제
        elif '길' in qt:
            addr_match = re.search(r'길\s*(\d+)', text)
            if addr_match:
                answer = addr_match.group(1)
                print(f"  📍 주소 숫자: {answer}")

        if answer:
            inp = await page.query_selector('input')
            btn = await page.query_selector('button:has-text("확인")')
            if inp and btn:
                await inp.fill(str(answer))
                await asyncio.sleep(0.3)
                await btn.click()
                print(f"  ✅ 답 입력: {answer}")
                await asyncio.sleep(3)
                return True
        else:
            print("  ❌ 답 추출 실패")

    except Exception as e:
        print(f"  오류: {e}")

    return False


async def main():
    NAVER_ID = "starkjy0112"
    NAVER_PW = "Wodud0228@##"

    pw = await async_playwright().start()
    browser = await pw.chromium.launch_persistent_context(
        user_data_dir='/tmp/naver_full_test',
        headless=False,
        locale='ko-KR',
        viewport={'width': 1280, 'height': 900}
    )

    try:
        page = browser.pages[0] if browser.pages else await browser.new_page()

        # ========== 1. 네이버 로그인 ==========
        print("\n" + "=" * 60)
        print("1. 네이버 로그인")
        print("=" * 60)

        # 로그인 상태 확인
        await page.goto('https://www.naver.com')
        await asyncio.sleep(2)

        cookies = await browser.cookies()
        logged_in = any('NID_AUT' in c.get('name', '') or 'NID_SES' in c.get('name', '') for c in cookies)

        if not logged_in:
            print("   로그인 진행...")
            await page.goto('https://nid.naver.com/nidlogin.login')
            await asyncio.sleep(2)

            try:
                await page.locator('#id').fill(NAVER_ID)
                await asyncio.sleep(0.5)
                await page.locator('#pw').fill(NAVER_PW)
                await asyncio.sleep(0.5)
                await page.locator('#log\\.login').click()
                await asyncio.sleep(5)
                print("   ✅ 로그인 버튼 클릭")
            except Exception as e:
                print(f"   로그인 오류: {e}")

            # 추가 인증 대기
            if 'nidlogin' in page.url:
                print("   ⚠️ 추가 인증이 필요합니다. 30초 대기...")
                await asyncio.sleep(30)
        else:
            print("   ✅ 이미 로그인됨")

        # ========== 2. 상품 페이지 (CAPTCHA 해결) ==========
        print("\n" + "=" * 60)
        print("2. 상품 페이지 접속 (CAPTCHA 해결)")
        print("=" * 60)

        url = "https://smartstore.naver.com/main/products/7255034137"
        print(f"   URL: {url}")

        max_attempts = 15
        for attempt in range(max_attempts):
            try:
                await page.goto(url, wait_until='domcontentloaded', timeout=20000)
            except:
                pass
            await asyncio.sleep(2)

            content = await page.content()

            # CAPTCHA 확인
            if '보안 확인' in content or '빈 칸' in content:
                print(f"\n   [CAPTCHA {attempt + 1}/{max_attempts}]")
                solved = await solve_captcha(page)
                if not solved:
                    await asyncio.sleep(5)
                continue

            # 운영 중지 확인
            if '운영이 중지' in content or '운영되고 있지' in content:
                print("   ❌ 운영 중지된 상품")
                break

            # 성공
            title = await page.title()
            if title and '운영' not in title:
                print(f"\n   ✅ 상품 페이지 접속 성공!")
                print(f"   제목: {title[:40]}...")
                break

        # ========== 3. 판매자 정보 추출 ==========
        print("\n" + "=" * 60)
        print("3. 판매자 정보 추출")
        print("=" * 60)

        # 스크롤
        await page.evaluate('window.scrollTo(0, 1500)')
        await asyncio.sleep(1)

        # 판매자정보 탭 클릭
        try:
            tab = page.locator('text=판매자정보').first
            if await tab.is_visible(timeout=3000):
                await tab.click()
                print("   ✅ 판매자정보 탭 클릭")
                await asyncio.sleep(2)
        except:
            pass

        # 더 스크롤
        await page.evaluate('window.scrollTo(0, 2000)')
        await asyncio.sleep(1)

        # 판매자 상세정보 버튼 클릭
        try:
            btn = page.locator('button:has-text("판매자 상세정보 확인")').first
            if await btn.is_visible(timeout=3000):
                await btn.scroll_into_view_if_needed()
                await asyncio.sleep(0.5)
                await btn.click()
                print("   ✅ 판매자 상세정보 버튼 클릭")
                await asyncio.sleep(3)
        except Exception as e:
            print(f"   버튼 클릭 실패: {e}")

        # 스크린샷
        await page.screenshot(path='/tmp/seller_result.png')
        print("   스크린샷: /tmp/seller_result.png")

        # ========== 4. 결과 ==========
        print("\n" + "=" * 60)
        print("4. 결과")
        print("=" * 60)

        content = await page.content()

        # 로그인 필요 확인
        if '로그인이 필요' in content:
            print("   ⚠️ 로그인이 필요한 서비스입니다!")
        else:
            # 전화번호 추출
            phone_patterns = [
                r'전화번호[:\s]*(\d{2,4}[-\s]?\d{3,4}[-\s]?\d{4})',
                r'대표전화[:\s]*(\d{2,4}[-\s]?\d{3,4}[-\s]?\d{4})',
                r'연락처[:\s]*(\d{2,4}[-\s]?\d{3,4}[-\s]?\d{4})',
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

            # 기타 판매자 정보
            info_patterns = [
                (r'대표자[:\s]*([가-힣]{2,5})', '대표자'),
                (r'상호[명:\s]*([가-힣a-zA-Z0-9]+)', '상호명'),
                (r'사업자등록번호[:\s]*([\d-]+)', '사업자번호'),
            ]

            for pat, name in info_patterns:
                m = re.search(pat, content)
                if m:
                    val = m.group(1)
                    if '220-81-62517' not in val:  # 네이버 사업자번호 제외
                        print(f"   {name}: {val}")

        print("\n60초 대기 (브라우저에서 직접 확인)...")
        await asyncio.sleep(60)

    finally:
        await browser.close()
        await pw.stop()


if __name__ == '__main__':
    asyncio.run(main())
