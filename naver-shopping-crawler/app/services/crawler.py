import asyncio
import re
import os
from typing import Optional, List
try:
    from patchright.async_api import async_playwright
except ImportError:
    from playwright.async_api import async_playwright
try:
    import easyocr
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
from app.config import CRAWL_DELAY, MAX_CONCURRENT_CRAWL


class PhoneCrawler:
    """스마트스토어 전화번호 크롤러 (Patchright 기반 + CAPTCHA 해결)"""

    def __init__(self):
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_CRAWL)
        self.browser = None
        self.playwright = None
        # 캐시: 스토어명 -> 전화번호
        self._phone_cache = {}
        # OCR 리더 (지연 초기화)
        self._ocr_reader = None
        # 로그인 프로필 경로
        self.user_data_dir = '/tmp/naver_crawler_profile'

    def _get_ocr_reader(self):
        """OCR 리더 지연 초기화"""
        if self._ocr_reader is None and OCR_AVAILABLE:
            self._ocr_reader = easyocr.Reader(['ko', 'en'], gpu=False)
        return self._ocr_reader

    async def init_browser(self):
        """브라우저 초기화 (Patchright 사용)"""
        if self.browser is None:
            self.playwright = await async_playwright().start()
            # 지속적인 브라우저 컨텍스트 사용 (로그인 상태 유지)
            self.browser = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=self.user_data_dir,
                headless=False,  # CAPTCHA 해결을 위해 headless=False
                locale='ko-KR',
                viewport={'width': 1280, 'height': 900},
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ]
            )

    async def close_browser(self):
        """브라우저 종료"""
        if self.browser:
            await self.browser.close()
            self.browser = None
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None

    async def _create_page(self):
        """페이지 생성 (persistent context용)"""
        # persistent context는 이미 브라우저 자체가 컨텍스트임
        page = await self.browser.new_page()
        return page

    async def _solve_captcha(self, page) -> bool:
        """CAPTCHA 자동 해결 (OCR 기반)"""
        if not OCR_AVAILABLE:
            print("OCR 사용 불가 - easyocr 설치 필요")
            return False

        try:
            # 질문 찾기
            question_elem = await page.query_selector('text=/빈 칸|번째/')
            if not question_elem:
                return False

            question_text = await question_elem.inner_text()
            print(f"  CAPTCHA 질문: {question_text[:50]}...")

            # 이미지 찾기
            img = await page.query_selector('img')
            if not img:
                return False

            # 이미지 저장 및 OCR
            await img.screenshot(path='/tmp/captcha_temp.png')
            reader = self._get_ocr_reader()
            if not reader:
                return False

            ocr_results = reader.readtext('/tmp/captcha_temp.png')
            ocr_text = ' '.join([r[1] for r in ocr_results])
            print(f"  OCR 결과: {ocr_text[:60]}...")

            answer = None

            # 전화번호 문제
            if '전화번호' in question_text:
                direction = '앞' if '앞에서' in question_text else '뒤'
                pos_match = re.search(r'(\d+)번째', question_text)
                pos = int(pos_match.group(1)) if pos_match else 1

                # 전화번호 패턴 찾기
                phone_match = re.search(r'(\d{3,4})[-\s](\d{4})', ocr_text)
                if phone_match:
                    digits = phone_match.group(1) + phone_match.group(2)
                    answer = digits[pos - 1] if direction == '앞' else digits[-pos]
                    print(f"  전화번호: {digits}, {direction}에서 {pos}번째 = {answer}")

            # 주소 문제
            elif '길' in question_text:
                addr_match = re.search(r'길\s*(\d+)', ocr_text)
                if addr_match:
                    answer = addr_match.group(1)
                    print(f"  주소 숫자: {answer}")

            if answer:
                inp = await page.query_selector('input')
                btn = await page.query_selector('button:has-text("확인")')
                if inp and btn:
                    await inp.fill(str(answer))
                    await asyncio.sleep(0.3)
                    await btn.click()
                    await asyncio.sleep(2)
                    return True

        except Exception as e:
            print(f"  CAPTCHA 해결 오류: {e}")

        return False

    async def get_phone_number(self, product_url: str, store_name: str = None) -> Optional[str]:
        """
        상품 URL에서 판매자 전화번호 추출

        Args:
            product_url: 네이버 쇼핑 상품 URL
            store_name: 스토어명 (캐시용)

        Returns:
            전화번호 또는 None

        Note:
            판매자 상세정보(전화번호)를 보려면 네이버 로그인이 필요합니다.
            처음 실행 시 브라우저에서 직접 로그인해주세요.
        """
        async with self.semaphore:
            try:
                # 캐시 확인
                if store_name and store_name in self._phone_cache:
                    return self._phone_cache[store_name]

                await asyncio.sleep(CRAWL_DELAY)

                # 스마트스토어 URL인지 확인
                if "smartstore.naver.com" not in product_url and "brand.naver.com" not in product_url:
                    print(f"스마트스토어 URL이 아님: {product_url}")
                    return None

                await self.init_browser()
                page = await self._create_page()

                try:
                    # CAPTCHA 해결 루프
                    for attempt in range(5):
                        try:
                            await page.goto(product_url, wait_until="domcontentloaded", timeout=20000)
                        except:
                            pass
                        await asyncio.sleep(2)

                        content = await page.content()

                        # CAPTCHA 확인
                        if '보안 확인' in content or '빈 칸' in content:
                            print(f"  CAPTCHA 감지 (시도 {attempt + 1}/5)")
                            solved = await self._solve_captcha(page)
                            if not solved:
                                await asyncio.sleep(5)
                            continue

                        # 운영 중지 확인
                        if '운영이 중지' in content or '운영되고 있지' in content:
                            print(f"  운영 중지된 상품: {product_url}")
                            return None

                        # 성공
                        break

                    # 전화번호 추출
                    phone = await self._extract_phone_from_page(page)

                    if phone and store_name:
                        self._phone_cache[store_name] = phone

                    return phone

                finally:
                    await page.close()

            except Exception as e:
                print(f"크롤링 오류 ({product_url}): {e}")
                return None

    async def _extract_phone_from_page(self, page) -> Optional[str]:
        """페이지에서 전화번호 추출 (판매자 상세정보 모달에서)"""
        try:
            # 1. 페이지 스크롤하여 판매자정보 영역 찾기
            await page.evaluate('window.scrollTo(0, 1500)')
            await asyncio.sleep(1)

            # 2. 판매자정보 탭 클릭
            try:
                tab = page.locator('text=판매자정보').first
                if await tab.is_visible(timeout=2000):
                    await tab.click()
                    await asyncio.sleep(1)
            except:
                pass

            # 3. 판매자 상세정보 버튼 클릭
            await page.evaluate('window.scrollTo(0, 2000)')
            await asyncio.sleep(1)

            detail_btn = page.locator('button:has-text("판매자 상세정보 확인")').first
            try:
                if await detail_btn.is_visible(timeout=2000):
                    await detail_btn.scroll_into_view_if_needed()
                    await asyncio.sleep(0.5)
                    await detail_btn.click()
                    await asyncio.sleep(3)
            except:
                pass

            # 4. 모달에서 전화번호 추출
            page_content = await page.content()

            # 로그인 필요 메시지 확인
            if '로그인이 필요' in page_content:
                print("  ⚠️ 전화번호 확인에 로그인이 필요합니다.")
                return None

            # 모달 내용에서 전화번호 찾기
            # "전화번호" 라벨 다음의 번호만 추출
            phone_patterns = [
                r'전화번호[:\s]*(\d{2,4}[-\s]?\d{3,4}[-\s]?\d{4})',
                r'대표전화[:\s]*(\d{2,4}[-\s]?\d{3,4}[-\s]?\d{4})',
                r'연락처[:\s]*(\d{2,4}[-\s]?\d{3,4}[-\s]?\d{4})',
            ]

            for pattern in phone_patterns:
                match = re.search(pattern, page_content)
                if match:
                    phone = match.group(1)
                    # 네이버 고객센터 번호 제외
                    if '1588-3819' not in phone and '1588-3816' not in phone:
                        return self._format_phone(phone)

            # 모달 요소에서 직접 찾기
            modal_selectors = ['[class*="Modal"]', '[class*="Layer"]', '[role="dialog"]']
            for sel in modal_selectors:
                try:
                    modal = page.locator(sel)
                    if await modal.count() > 0:
                        for i in range(await modal.count()):
                            elem = modal.nth(i)
                            if await elem.is_visible(timeout=500):
                                text = await elem.inner_text()
                                if '전화번호' in text or '대표자' in text:
                                    for pattern in phone_patterns:
                                        match = re.search(pattern, text)
                                        if match:
                                            phone = match.group(1)
                                            if '1588-3819' not in phone:
                                                return self._format_phone(phone)
                except:
                    continue

            return None

        except Exception as e:
            print(f"전화번호 추출 오류: {e}")
            return None

    def _format_phone(self, phone: str) -> str:
        """전화번호 포맷팅"""
        if "-" in phone:
            return phone

        phone = re.sub(r"[^0-9]", "", phone)

        if not phone:
            return ""

        if phone.startswith("02"):
            if len(phone) == 9:
                return f"{phone[:2]}-{phone[2:5]}-{phone[5:]}"
            else:
                return f"{phone[:2]}-{phone[2:6]}-{phone[6:]}"
        elif phone.startswith("01"):
            return f"{phone[:3]}-{phone[3:7]}-{phone[7:]}"
        elif phone.startswith("1"):
            return f"{phone[:4]}-{phone[4:]}"
        elif len(phone) >= 10:
            return f"{phone[:3]}-{phone[3:6]}-{phone[6:]}"
        else:
            return phone

    async def get_phone_by_store_name(self, store_name: str) -> Optional[str]:
        """스토어명으로 직접 전화번호 조회"""
        if store_name in self._phone_cache:
            return self._phone_cache[store_name]

        store_url = f"https://smartstore.naver.com/{store_name}"

        async with self.semaphore:
            try:
                await asyncio.sleep(CRAWL_DELAY)
                await self.init_browser()
                page = await self._create_page()

                try:
                    # CAPTCHA 해결 루프
                    for attempt in range(5):
                        try:
                            await page.goto(store_url, wait_until="domcontentloaded", timeout=20000)
                        except:
                            pass
                        await asyncio.sleep(2)

                        content = await page.content()
                        if '보안 확인' in content:
                            await self._solve_captcha(page)
                            continue
                        break

                    phone = await self._extract_phone_from_page(page)

                    if phone:
                        self._phone_cache[store_name] = phone

                    return phone

                finally:
                    await page.close()

            except Exception as e:
                print(f"전화번호 조회 오류 ({store_name}): {e}")
                return None

    async def crawl_batch(self, items: List[dict]) -> List[Optional[str]]:
        """여러 상품 배치 크롤링"""
        await self.init_browser()

        tasks = []
        for item in items:
            if isinstance(item, dict):
                tasks.append(self.get_phone_number(
                    item.get("url", ""),
                    item.get("store_name")
                ))
            else:
                tasks.append(self.get_phone_number(item))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        return [
            r if isinstance(r, str) else None
            for r in results
        ]


# 싱글톤 인스턴스
phone_crawler = PhoneCrawler()
