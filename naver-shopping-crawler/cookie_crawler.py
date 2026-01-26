"""
쿠키 저장 & 재사용 방식 크롤러 (undetected-chromedriver)
1. 처음: 브라우저 열고 수동 로그인 → 쿠키 저장
2. 이후: 저장된 쿠키로 자동 접근
"""
import json
import os
import time
import re
import shutil
import sys
import tty
import termios
from datetime import datetime
import undetected_chromedriver as uc


def getch():
    """Enter 없이 한 글자 입력 받기"""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import cv2
import numpy as np
from paddleocr import PaddleOCR

COOKIE_FILE = '/tmp/naver_cookies.json'
CAPTCHA_DATASET_DIR = '/Users/teramime/Documents/project_20/naver-shopping-crawler/captcha_images'

# 데이터셋 폴더 생성
os.makedirs(CAPTCHA_DATASET_DIR, exist_ok=True)

# OCR 리더 (PaddleOCR)
ocr_reader = None
def get_ocr():
    global ocr_reader
    if ocr_reader is None:
        print("   PaddleOCR 초기화 중...")
        ocr_reader = PaddleOCR(lang='korean', device='cpu')
    return ocr_reader


def paddle_to_easyocr_format(paddle_result):
    """PaddleOCR 결과를 EasyOCR 형식으로 변환

    새 PaddleOCR 형식 (OCRResult 객체):
    result['rec_texts'], result['rec_scores'], result['rec_polys']

    EasyOCR 형식:
    [[[x1,y1], [x2,y2], [x3,y3], [x4,y4]], text, confidence]
    """
    if not paddle_result:
        return []

    first = paddle_result[0]

    # 새 API: OCRResult 객체 ([] 인덱싱 지원)
    try:
        texts = first['rec_texts']
        scores = first['rec_scores']
        boxes = first['rec_polys']

        converted = []
        for i in range(len(texts)):
            text = texts[i]
            score = scores[i] if i < len(scores) else 0.0
            box = boxes[i] if i < len(boxes) else [[0, 0], [0, 0], [0, 0], [0, 0]]

            # rec_polys는 이미 4점 형식 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            converted.append([box, text, score])
        return converted
    except (KeyError, TypeError):
        pass

    # 구 API 형식 (리스트)
    try:
        converted = []
        for line in paddle_result[0]:
            bbox = line[0]
            text = line[1][0]
            conf = line[1][1]
            converted.append([bbox, text, conf])
        return converted
    except:
        return []


def preprocess_image(image_path):
    """이미지 전처리 - OCR 정확도 향상"""
    img = cv2.imread(image_path)
    if img is None:
        return image_path

    # 그레이스케일 변환
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 대비 향상 (CLAHE)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # 노이즈 제거
    denoised = cv2.fastNlMeansDenoising(enhanced, None, 10, 7, 21)

    # 이진화 (적응형 임계값)
    binary = cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )

    # 전처리된 이미지 저장
    processed_path = '/tmp/captcha_processed.png'
    cv2.imwrite(processed_path, binary)

    return processed_path


def parse_receipt_table(ocr_result):
    """
    EasyOCR 결과에서 영수증 테이블 구조 파싱
    반환: {'단가': [...], '수량': [...], '합계': [...], 'total': int, 'item_count': int}

    easyocr 반환 형식: [(bbox, text, confidence), ...]
    bbox는 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]

    지원하는 영수증 형식:
    1. 단가 | 수량 | 합계 형식
    2. 합(계) | 개수 형식

    주의: 이미지에 여러 영수증이 있을 수 있으므로 X좌표로 영수증을 분리하여 처리
    """
    if not ocr_result:
        return None

    # OCR 결과에서 텍스트와 위치 정보 추출
    all_items = []
    for line in ocr_result:
        bbox = line[0]
        text = line[1]
        confidence = line[2]

        center_x = (bbox[0][0] + bbox[2][0]) / 2
        center_y = (bbox[0][1] + bbox[2][1]) / 2

        all_items.append({
            'text': text,
            'x': center_x,
            'y': center_y,
            'conf': confidence
        })

    print(f"   OCR 항목 수: {len(all_items)}")

    # X 좌표로 영수증 그룹 분리 (클러스터링)
    # 먼저 X 좌표 분포 확인
    x_coords = sorted([item['x'] for item in all_items])

    # 영수증 그룹 경계 찾기 (X 좌표 갭이 100px 이상이면 다른 영수증)
    receipt_groups = []
    current_group = []
    last_x = None

    for item in sorted(all_items, key=lambda x: x['x']):
        if last_x is None or item['x'] - last_x < 100:
            current_group.append(item)
        else:
            if current_group:
                receipt_groups.append(current_group)
            current_group = [item]
        last_x = item['x']

    if current_group:
        receipt_groups.append(current_group)

    print(f"   영수증 그룹 수: {len(receipt_groups)}")

    # 각 영수증 그룹별로 파싱하여 가장 유효한 결과 반환
    best_result = None
    best_total = 0

    for group_idx, items in enumerate(receipt_groups):
        group_result = parse_single_receipt(items, group_idx)
        if group_result:
            # 합계가 가장 높거나 개수가 가장 많은 영수증 선택
            current_total = group_result['total'] or sum(group_result['합계'])
            current_count = group_result['item_count'] or sum(group_result['수량'])

            if current_total > best_total or (current_total == 0 and current_count > 0):
                best_result = group_result
                best_total = current_total

    return best_result


def parse_single_receipt(items, group_idx=0):
    """단일 영수증 파싱"""
    if not items:
        return None

    # Y 좌표로 정렬
    items = sorted(items, key=lambda x: x['y'])

    print(f"   [영수증 {group_idx + 1}] 항목 수: {len(items)}")

    # 헤더 패턴 감지
    header_y = None
    col_positions = {'합': None, '개수': None, '단가': None, '수량': None, '합계': None}

    for item in items:
        text = item['text']
        # OCR 오류 수정: 숫자/영어 제거하여 순수 한글 추출
        korean_only = re.sub(r'[^가-힣]', '', text)

        # "합계" 열
        if korean_only == '합계' or '합계' in text:
            col_positions['합계'] = item['x']
            header_y = item['y']
        # "합" 열 (8합 → 합)
        elif korean_only == '합' or '합' in korean_only:
            col_positions['합'] = item['x']
            if header_y is None:
                header_y = item['y']
        # "값" 열
        elif korean_only == '값':
            col_positions['합'] = item['x']
            if header_y is None:
                header_y = item['y']
        # "개수" 열 (개76 → 개수 또는 개)
        elif korean_only in ['개수', '개']:
            col_positions['개수'] = item['x']
            if header_y is None:
                header_y = item['y']
        # "단가" 열
        elif '단가' in text:
            col_positions['단가'] = item['x']
            if header_y is None:
                header_y = item['y']
        # "수량" 열
        elif '수량' in text:
            col_positions['수량'] = item['x']
            if header_y is None:
                header_y = item['y']

    print(f"   헤더 위치: {col_positions}")

    if header_y is None:
        return None

    # 헤더 간 X 거리 확인 - 150px 이상 떨어져 있으면 다른 영수증의 헤더
    # 이 경우 더 완전한 영수증을 선택하거나 각각 처리
    sum_x = col_positions['합']
    count_x = col_positions['개수']

    if sum_x is not None and count_x is not None:
        header_distance = abs(sum_x - count_x)
        if header_distance > 150:
            # 헤더가 다른 영수증에 있음 - 가까운 데이터가 많은 헤더 선택
            print(f"   주의: 합({sum_x:.0f})과 개수({count_x:.0f}) 헤더가 {header_distance:.0f}px 떨어져 있음 (다른 영수증)")

            # 각 헤더 주변의 숫자 항목 수 카운트
            sum_nearby_count = sum(1 for item in items if item['y'] > header_y + 10 and abs(item['x'] - sum_x) < 100)
            count_nearby_count = sum(1 for item in items if item['y'] > header_y + 10 and abs(item['x'] - count_x) < 100)

            print(f"   합 근처 항목: {sum_nearby_count}개, 개수 근처 항목: {count_nearby_count}개")

            # 더 많은 데이터가 있는 쪽 선택
            if count_nearby_count > sum_nearby_count:
                col_positions['합'] = None  # 개수만 있는 것으로 처리
                print(f"   → 개수 헤더 기준으로 처리 (has_count_only)")
            else:
                col_positions['개수'] = None  # 합만 있는 것으로 처리
                print(f"   → 합 헤더 기준으로 처리")

    # 영수증 형식 결정
    # 1. "합|개수" 형식 (합, 개수 둘 다 있음 - 같은 영수증)
    # 2. "개수" 열만 있는 형식 (값 헤더가 OCR에서 누락된 경우)
    # 3. "합계" 열만 있는 형식
    # 4. "단가|수량|합계" 형식
    is_sum_count_format = col_positions['합'] is not None and col_positions['개수'] is not None
    has_count_only = col_positions['개수'] is not None and col_positions['합'] is None and col_positions['합계'] is None
    has_total_column = col_positions['합계'] is not None

    result = {'단가': [], '수량': [], '합계': [], 'total': 0, 'item_count': 0}

    if has_total_column:
        print("   형식: 합계 열")
        # "합계" 열 아래의 숫자만 추출
        total_col_x = col_positions['합계']

        for item in items:
            if item['y'] <= header_y + 10:
                continue

            x = item['x']

            # "합계" 열 근처 (80픽셀 이내)
            if abs(x - total_col_x) > 80:
                continue

            # 텍스트에서 숫자 비율이 높은지 확인 (숫자만 있는 항목)
            text = item['text']

            # 일반적인 OCR 오류 수정
            # O → 0, I → 1, l → 1, J → 1, B → 8, S → 5, G → 6
            cleaned = text.upper()
            cleaned = cleaned.replace('O', '0').replace('I', '1').replace('L', '1').replace('J', '1')
            cleaned = cleaned.replace('B', '8').replace('S', '5').replace('G', '6')

            digits_only = re.sub(r'[^0-9]', '', cleaned)
            if len(digits_only) == 0:
                continue

            # 숫자 비율이 50% 이상이면 숫자 항목으로 간주
            if len(digits_only) / len(text) < 0.5:
                continue

            val = int(digits_only)

            # 끝자리가 00이 아닌 5자리 숫자는 마지막 자리 제거 (OCR 노이즈)
            # 예: 45009 → 4500
            if 10000 <= val <= 99999 and val % 100 != 0:
                val = val // 10

            # 유효한 가격 범위 (100 ~ 99999)
            if 100 <= val <= 99999:
                result['합계'].append(val)
                print(f"      합계 추출: '{text}' → {val}")

        print(f"   합계 열 항목: {result['합계']}")

    elif is_sum_count_format:
        print("   형식: 합|개수 (값|개수)")
        # 헤더 열 위치를 기준으로 해당 열 아래의 숫자만 추출
        sum_col_x = col_positions['합']
        count_col_x = col_positions['개수']

        # 헤더 아래 데이터에서 숫자 추출하고, 더 가까운 열에 할당
        sum_items = []
        count_items = []

        for item in items:
            if item['y'] <= header_y + 10:
                continue

            text = item['text'].strip()

            # 텍스트에서 선행 숫자 추출 (노이즈 포함 시 앞쪽 숫자만)
            # 예: "30/8H3" → "30", "70C" → "70", "10v" → "10"
            leading_match = re.match(r'^(\d+)', text)
            if not leading_match:
                # 선행 숫자가 없으면 텍스트에서 숫자만 추출
                digits_only = re.sub(r'[^0-9]', '', text)
                if len(digits_only) == 0:
                    continue
                # 순수 숫자가 아니면 스킵 (노이즈 섞인 경우)
                if len(digits_only) != len(text):
                    continue
            else:
                digits_only = leading_match.group(1)

            x = item['x']

            # 각 열과의 거리 계산
            dist_to_sum = abs(x - sum_col_x) if sum_col_x else float('inf')
            dist_to_count = abs(x - count_col_x) if count_col_x else float('inf')

            # 최소 거리가 100픽셀 이내인 경우만 처리
            min_dist = min(dist_to_sum, dist_to_count)
            if min_dist > 100:
                continue

            val = int(digits_only)

            # 더 가까운 열에 할당
            if dist_to_sum < dist_to_count:
                # 값/합계 열 (보통 큰 숫자)
                sum_items.append({'value': val, 'y': item['y'], 'text': text})
            else:
                # 개수 열 (보통 1-2자리 작은 숫자)
                # 개수가 너무 크면 OCR 오류일 가능성
                # 1~30 범위만 허용, 10의 배수이고 >10이면 가격일 가능성 높음
                if val <= 30 and not (val > 10 and val % 10 == 0):
                    count_items.append({'value': val, 'y': item['y'], 'text': text})

        # Y 좌표로 정렬
        sum_items.sort(key=lambda x: x['y'])
        count_items.sort(key=lambda x: x['y'])

        # 결과 추출
        result['합계'] = [item['value'] for item in sum_items]
        result['수량'] = [item['value'] for item in count_items]

        print(f"   합계(값) 열 항목: {result['합계']}")
        print(f"   개수 열 항목: {result['수량']}")

    elif has_count_only:
        # 개수 열만 감지된 경우 (값 헤더가 OCR에서 누락)
        # 개수 헤더 왼쪽에 있는 숫자들을 값으로, 개수 헤더 근처를 개수로 처리
        print("   형식: 개수 열만 감지 (값 열 추정)")
        count_col_x = col_positions['개수']

        # 해당 영수증 영역 추정 (개수 헤더 기준 ±100픽셀)
        receipt_x_min = count_col_x - 100
        receipt_x_max = count_col_x + 50

        sum_items = []
        count_items = []

        for item in items:
            if item['y'] <= header_y + 10:
                continue

            x = item['x']

            # 해당 영수증 영역 내의 항목만 처리
            if x < receipt_x_min or x > receipt_x_max:
                continue

            text = item['text'].strip()

            # 텍스트에서 선행 숫자 추출
            leading_match = re.match(r'^(\d+)', text)
            if not leading_match:
                digits_only = re.sub(r'[^0-9]', '', text)
                if len(digits_only) == 0:
                    continue
                if len(digits_only) != len(text):
                    continue
            else:
                digits_only = leading_match.group(1)

            val = int(digits_only)

            # 개수 헤더 왼쪽 (x < count_col_x - 20) = 값 열
            # 개수 헤더 근처 (x >= count_col_x - 20) = 개수 열
            if x < count_col_x - 20:
                sum_items.append({'value': val, 'y': item['y'], 'text': text})
                print(f"      값 추출: [{x:.0f}] '{text}' → {val}")
            else:
                if val <= 30 and not (val > 10 and val % 10 == 0):
                    count_items.append({'value': val, 'y': item['y'], 'text': text})
                    print(f"      개수 추출: [{x:.0f}] '{text}' → {val}")

        sum_items.sort(key=lambda x: x['y'])
        count_items.sort(key=lambda x: x['y'])

        result['합계'] = [item['value'] for item in sum_items]
        result['수량'] = [item['value'] for item in count_items]

        print(f"   합계(값) 열 항목: {result['합계']}")
        print(f"   개수 열 항목: {result['수량']}")

    else:
        print("   형식: 단가|수량|합계 또는 자동 감지")

        # 헤더 아래 데이터 추출
        data_items = [item for item in items if item['y'] > header_y + 10]

        # Y 좌표 기준 행 그룹핑
        rows = []
        current_row = []
        last_y = None

        for item in data_items:
            if last_y is None or abs(item['y'] - last_y) < 20:
                current_row.append(item)
            else:
                if current_row:
                    rows.append(current_row)
                current_row = [item]
            last_y = item['y']

        if current_row:
            rows.append(current_row)

        print(f"   데이터 행 수: {len(rows)}")

        # 각 행에서 숫자들 추출
        for row in rows:
            row_sorted = sorted(row, key=lambda x: x['x'])
            numbers = []
            for item in row_sorted:
                nums = re.findall(r'\d+', item['text'])
                for num in nums:
                    val = int(num)
                    numbers.append(val)

            if len(numbers) >= 3:
                result['단가'].append(numbers[0])
                result['수량'].append(numbers[1])
                result['합계'].append(numbers[2])
            elif len(numbers) == 2:
                result['합계'].append(numbers[0])
                result['수량'].append(numbers[1])

    # 총합 및 총 개수 계산
    result['total'] = sum(result['합계']) if result['합계'] else 0
    result['item_count'] = sum(result['수량']) if result['수량'] else 0

    print(f"   파싱 결과: 합계={result['합계']}, 수량={result['수량']}")
    print(f"   총 구매 금액: {result['total']}, 총 개수: {result['item_count']}")

    return result


def save_cookies(driver):
    """쿠키를 파일로 저장"""
    cookies = driver.get_cookies()
    with open(COOKIE_FILE, 'w') as f:
        json.dump(cookies, f)
    print(f"   쿠키 저장됨: {COOKIE_FILE} ({len(cookies)}개)")


def load_cookies(driver):
    """저장된 쿠키 로드"""
    if not os.path.exists(COOKIE_FILE):
        return False

    with open(COOKIE_FILE, 'r') as f:
        cookies = json.load(f)

    # 먼저 네이버 도메인으로 이동 (쿠키 설정을 위해)
    driver.get('https://www.naver.com')
    time.sleep(1)

    for cookie in cookies:
        try:
            # sameSite 속성 제거 (호환성 문제)
            if 'sameSite' in cookie:
                del cookie['sameSite']
            driver.add_cookie(cookie)
        except Exception as e:
            pass

    print(f"   쿠키 로드됨: {len(cookies)}개")
    return True


def solve_captcha(driver):
    """CAPTCHA 해결 시도"""
    try:
        page_source = driver.page_source or ""

        # 질문 찾기 (HTML 태그 제거 후)
        # 먼저 HTML 태그 제거
        import html
        clean_text = re.sub(r'<[^>]+>', ' ', page_source)
        clean_text = html.unescape(clean_text)

        question = None
        q_patterns = [
            r'(영수증에서[^?]{5,50}\?)',
            r'(전화번호의?\s*\d*번째[^?]+\?)',
            r'(앞에서\s*\d+번째[^?]+\?)',
            r'(뒤에서\s*\d+번째[^?]+\?)',
            r'(빈\s*칸[^?]+\?)',
            r'(몇\s*개[^?]+\?)',
            r'(총\s*구매\s*금액[^?]+\?)',
            r'(총\s*금액[^?]+\?)',
            r'(얼마입니까[^?]*\?)',
        ]
        for pat in q_patterns:
            match = re.search(pat, clean_text)
            if match:
                question = match.group(1).strip()
                break

        if not question:
            print("   질문을 찾지 못함")
            return False

        print(f"   질문: {question[:80]}...")

        # CAPTCHA 팝업/이미지 캡처
        captcha_img_path = '/tmp/captcha_img.png'
        try:
            # 방법 1: 모달/팝업 내 이미지 찾기
            img_selectors = [
                "//div[contains(@class, 'modal')]//img",
                "//div[contains(@class, 'popup')]//img",
                "//div[contains(@class, 'captcha')]//img",
                "//div[contains(@class, 'layer')]//img",
                "//img[contains(@src, 'captcha')]",
                "//img[contains(@src, 'receipt')]",
                "//img[contains(@alt, '영수증')]",
            ]
            img = None
            for sel in img_selectors:
                try:
                    img = driver.find_element(By.XPATH, sel)
                    if img and img.size['width'] > 50:  # 최소 크기 확인
                        break
                except:
                    continue

            if img and img.size['width'] > 50:
                img.screenshot(captcha_img_path)
                print(f"   CAPTCHA 이미지 캡처: {img.size}")
            else:
                # 방법 2: 모달 전체 캡처
                modal_selectors = [
                    "//div[contains(@class, 'modal')]",
                    "//div[contains(@class, 'popup')]",
                    "//div[contains(@class, 'layer')]",
                    "//div[contains(@class, 'captcha')]",
                ]
                modal = None
                for sel in modal_selectors:
                    try:
                        modal = driver.find_element(By.XPATH, sel)
                        if modal and modal.size['width'] > 100:
                            break
                    except:
                        continue

                if modal and modal.size['width'] > 100:
                    modal.screenshot(captcha_img_path)
                    print(f"   모달 전체 캡처: {modal.size}")
                else:
                    # 방법 3: 전체 화면 캡처
                    driver.save_screenshot(captcha_img_path)
                    print("   전체 화면 캡처")
        except Exception as e:
            print(f"   이미지 캡처 실패: {e}")
            driver.save_screenshot(captcha_img_path)
            print("   전체 화면 캡처 (fallback)")

        # 데이터셋용 CAPTCHA 이미지 저장
        try:
            existing = [f for f in os.listdir(CAPTCHA_DATASET_DIR) if f.endswith('.png')]
            next_num = len(existing) + 1
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            dataset_filename = f"captcha_{next_num:04d}_{timestamp}.png"
            dataset_path = os.path.join(CAPTCHA_DATASET_DIR, dataset_filename)
            shutil.copy('/tmp/captcha_img.png', dataset_path)
            print(f"   📁 데이터셋 저장: {dataset_filename} (총 {next_num}개)")
        except Exception as e:
            print(f"   데이터셋 저장 실패: {e}")

        # 이미지 전처리
        processed_img = preprocess_image('/tmp/captcha_img.png')
        print(f"   전처리 이미지: {processed_img}")

        # PaddleOCR (원본 + 전처리 둘 다 시도)
        reader = get_ocr()

        paddle_result1 = reader.predict('/tmp/captcha_img.png')
        result1 = paddle_to_easyocr_format(paddle_result1)
        ocr_text1 = ' '.join([line[1] for line in result1]) if result1 else ''

        paddle_result2 = reader.predict(processed_img)
        result2 = paddle_to_easyocr_format(paddle_result2)
        ocr_text2 = ' '.join([line[1] for line in result2]) if result2 else ''

        # 더 많은 숫자를 추출한 결과 선택
        nums1 = re.findall(r'\d+', ocr_text1)
        nums2 = re.findall(r'\d+', ocr_text2)

        print(f"   OCR (원본): {ocr_text1[:200]}...")
        print(f"   OCR (전처리): {ocr_text2[:200]}...")

        if len(nums2) >= len(nums1):
            ocr_text = ocr_text2
            all_numbers = nums2
            ocr_result = result2  # 테이블 파싱용 (easyocr 형식으로 변환됨)
            print(f"   선택: 전처리 결과")
        else:
            ocr_text = ocr_text1
            all_numbers = nums1
            ocr_result = result1  # 테이블 파싱용 (easyocr 형식으로 변환됨)
            print(f"   선택: 원본 결과")

        print(f"   추출된 숫자들: {all_numbers}")

        answer = None

        # 영수증 - 총 몇 개 (수량/개수 합계)
        if '몇 개' in question or '몇개' in question:
            print("   질문 유형: 총 몇 개 (수량)")

            # 방법 1: 테이블 파싱 시도
            table_result = parse_receipt_table(ocr_result)

            if table_result and table_result.get('item_count', 0) > 0:
                answer = table_result['item_count']
                print(f"   ★ 테이블 파싱 성공: 수량 = {table_result['수량']} → 총 개수 = {answer}")
            elif table_result and table_result['수량']:
                answer = sum(table_result['수량'])
                print(f"   ★ 테이블 파싱: 수량 = {table_result['수량']} → {answer}")
            else:
                # 방법 2: 단순 휴리스틱 - 1~9 사이 단일 숫자만 합산
                # 영수증에서 수량은 보통 1자리 숫자 (1~9)
                print("   테이블 파싱 실패, 단순 휴리스틱 사용...")
                single_digits = []
                for item in ocr_result:
                    text = item[1].strip()
                    # 정확히 1자리 숫자인 경우만
                    if text.isdigit() and len(text) == 1 and text != '0':
                        single_digits.append(int(text))
                if single_digits:
                    answer = sum(single_digits)
                    print(f"   ★ 1자리 숫자들: {single_digits} → 합계: {answer}")
                else:
                    # 방법 3: OCR 텍스트에서 추출
                    numbers = re.findall(r'\b([1-9])\b', ocr_text)
                    if numbers:
                        single_digits = [int(n) for n in numbers]
                        answer = sum(single_digits)
                        print(f"   ★ 텍스트에서 1자리 숫자: {single_digits} → 합계: {answer}")
                    else:
                        print("   ★ 수량 추출 실패")

        # 전화번호 N번째 숫자
        elif '전화번호' in question or '번째' in question:
            direction = '앞' if '앞에서' in question else '뒤'
            pos_match = re.search(r'(\d+)번째', question)
            pos = int(pos_match.group(1)) if pos_match else 1

            # 전화번호 패턴: XXX-XXXX 또는 XXXX-XXXX (하이픈 필수)
            phone_patterns = [
                r'(0\d{1,2})-(\d{3,4})-(\d{4})',  # 지역번호-국번-번호
                r'(\d{3,4})-(\d{4})',  # 국번-번호
            ]

            phone_match = None
            for pat in phone_patterns:
                matches = re.findall(pat, ocr_text)
                for m in matches:
                    if len(m) == 3:  # 지역번호 포함
                        full_num = m[0] + m[1] + m[2]
                        first_part = m[0]
                    else:  # 국번-번호만
                        full_num = m[0] + m[1]
                        first_part = m[0]

                    # 고객센터 번호 제외 (1588, 1544, 1577 등)
                    if first_part.startswith('1588') or first_part.startswith('1544') or first_part.startswith('1577'):
                        continue
                    # 길이 확인
                    if len(full_num) >= 7:
                        phone_match = m
                        break
                if phone_match:
                    break

            if phone_match:
                if len(phone_match) == 3:
                    digits = phone_match[0] + phone_match[1] + phone_match[2]
                else:
                    digits = phone_match[0] + phone_match[1]
                # 하이픈 제거한 순수 숫자
                digits = digits.replace('-', '')
                if pos <= len(digits):
                    answer = digits[pos - 1] if direction == '앞' else digits[-pos]
                    print(f"   전화번호: {digits}, {direction}에서 {pos}번째 = {answer}")
                else:
                    print(f"   전화번호: {digits}, 위치 {pos}가 범위 초과")

        # 주소 빈칸
        elif '길' in question or '빈 칸' in question:
            addr_match = re.search(r'길\s*(\d+)', ocr_text)
            if addr_match:
                answer = addr_match.group(1)
                print(f"   주소 숫자: {answer}")

        # 총 구매 금액
        elif '총 구매 금액' in question or '총 금액' in question or '얼마입니까' in question:
            # 방법 1: 테이블 파싱으로 합계 열의 총합 계산
            print("   영수증 테이블 파싱 시도...")
            table_result = parse_receipt_table(ocr_result)
            if table_result and table_result['total'] > 0:
                answer = table_result['total']
                print(f"   테이블 파싱 성공: 합계 열 총합 = {answer}")
            else:
                # 방법 2: "합계" 근처의 숫자 찾기
                print("   테이블 파싱 실패, 폴백 방법 시도...")
                total_patterns = [
                    r'합계[^\d]*(\d{1,6})',
                    r'총액[^\d]*(\d{1,6})',
                    r'총합[^\d]*(\d{1,6})',
                    r'TOTAL[^\d]*(\d{1,6})',
                    r'합[^\d]*(\d{4,6})',  # 4자리 이상
                ]
                for pat in total_patterns:
                    match = re.search(pat, ocr_text, re.IGNORECASE)
                    if match:
                        answer = int(match.group(1))
                        print(f"   합계 패턴 발견: {answer}")
                        break

                # 방법 3: 4자리 이상 숫자 중 가장 큰 것들의 합
                if not answer:
                    prices = re.findall(r'\b(\d{4,6})\b', ocr_text)
                    valid_prices = [int(p) for p in prices if 1000 <= int(p) <= 99999]
                    if valid_prices:
                        # 중복 제거 후 정렬
                        unique_prices = sorted(set(valid_prices), reverse=True)
                        # 가장 큰 4개 이하의 값만 합산 (행 개수 추정)
                        top_prices = unique_prices[:4]
                        total = sum(top_prices)
                        print(f"   폴백 가격들 (상위 4개): {top_prices}")
                        print(f"   폴백 합산: {total}")
                        answer = total

        # 답 확인
        if answer:
            print(f"   계산된 답: {answer}")

        if answer:
            # 입력 필드 찾기 (크기가 0이 아닌 보이는 요소만)
            inp = None
            input_selectors = [
                "//input[@placeholder='정답을 입력해주세요.']",
                "//input[contains(@placeholder, '정답')]",
                "//input[contains(@placeholder, '입력')]",
            ]

            # 여러 셀렉터로 모든 후보 찾기
            candidates = []
            for sel in input_selectors:
                try:
                    elements = driver.find_elements(By.XPATH, sel)
                    candidates.extend(elements)
                except:
                    continue

            # 모든 input 태그도 추가
            try:
                all_inputs = driver.find_elements(By.TAG_NAME, 'input')
                for i in all_inputs:
                    try:
                        inp_type = i.get_attribute('type')
                        if inp_type in ['text', 'number', '', None]:
                            if i not in candidates:
                                candidates.append(i)
                    except:
                        continue
            except:
                pass

            print(f"   입력 필드 후보 수: {len(candidates)}")

            # 크기가 0이 아닌 보이는 요소 찾기
            for candidate in candidates:
                try:
                    size = candidate.size
                    if size['width'] > 0 and size['height'] > 0:
                        inp = candidate
                        placeholder = candidate.get_attribute('placeholder') or ''
                        print(f"   입력 필드 발견: 크기={size}, placeholder={placeholder}")
                        break
                except:
                    continue

            if inp:
                # 입력 필드 정보 출력
                print(f"   입력 필드 위치: {inp.location}, 크기: {inp.size}")

                # 방법 1: 직접 click + send_keys (가장 기본적인 방식)
                try:
                    # 스크롤
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", inp)
                    time.sleep(0.5)

                    # 클릭하여 포커스
                    inp.click()
                    time.sleep(0.3)

                    # 값 입력
                    inp.send_keys(str(answer))
                    print(f"   답 입력 (send_keys): {answer}")

                    # 입력 확인
                    entered_val = inp.get_attribute('value')
                    print(f"   입력된 값 확인: {entered_val}")

                    if not entered_val or entered_val != str(answer):
                        raise Exception("입력값 확인 실패")

                except Exception as e:
                    print(f"   send_keys 실패: {e}")
                    # 방법 2: ActionChains
                    try:
                        actions = ActionChains(driver)
                        actions.move_to_element(inp).click().perform()
                        time.sleep(0.3)

                        # 기존 값 지우기
                        actions = ActionChains(driver)
                        actions.key_down(Keys.COMMAND).send_keys('a').key_up(Keys.COMMAND).perform()
                        time.sleep(0.1)
                        actions = ActionChains(driver)
                        actions.send_keys(Keys.BACKSPACE).perform()
                        time.sleep(0.1)

                        # 한 글자씩 입력
                        for char in str(answer):
                            actions = ActionChains(driver)
                            actions.send_keys(char).perform()
                            time.sleep(0.1)

                        print(f"   답 입력 (ActionChains): {answer}")
                    except Exception as e2:
                        print(f"   ActionChains 실패: {e2}")

                time.sleep(0.5)

                # 스크린샷 (입력 후)
                driver.save_screenshot('/tmp/after_input.png')
                print("   입력 후 스크린샷: /tmp/after_input.png")

                # 확인 버튼 찾기 및 클릭
                print("   확인 버튼 찾는 중...")
                btn_found = False

                # 모든 버튼 찾기
                all_buttons = driver.find_elements(By.TAG_NAME, 'button')
                print(f"   발견된 버튼 수: {len(all_buttons)}")

                for btn in all_buttons:
                    try:
                        btn_text = btn.text.strip()
                        if btn_text == '확인':
                            print(f"   '확인' 버튼 발견 - 위치: {btn.location}, 크기: {btn.size}")
                            # 버튼 클릭
                            btn.click()
                            print("   확인 버튼 클릭 완료!")
                            btn_found = True
                            break
                    except Exception as e:
                        continue

                if not btn_found:
                    print("   확인 버튼 못 찾음, Enter 키로 제출 시도...")
                    try:
                        inp.send_keys(Keys.RETURN)
                        print("   Enter 키 전송 완료")
                    except:
                        pass

                time.sleep(2)

                # 결과 스크린샷
                driver.save_screenshot('/tmp/after_confirm.png')
                print("   확인 후 스크린샷: /tmp/after_confirm.png")

                # CAPTCHA가 사라졌는지 확인
                time.sleep(1)
                new_page_source = driver.page_source or ""
                if '정답을 입력' not in new_page_source and '영수증에서' not in new_page_source:
                    print("   ✅ CAPTCHA 해결 성공!")
                    return True
                else:
                    print("   ❌ CAPTCHA 아직 남아있음 (오답일 수 있음)")
                    return False
            else:
                print("   입력 필드를 찾지 못함")

    except Exception as e:
        print(f"   CAPTCHA 오류: {e}")

    return False


def manual_login():
    """수동 로그인 모드 - 쿠키 저장"""
    print("=" * 60)
    print("수동 로그인 모드")
    print("=" * 60)
    print("1. 브라우저가 열리면 네이버에 로그인하세요")
    print("2. 로그인 완료 후 Enter를 누르세요")
    print("=" * 60)

    options = uc.ChromeOptions()
    options.add_argument("--lang=ko-KR")
    driver = uc.Chrome(options=options, version_main=143)

    try:
        driver.get('https://nid.naver.com/nidlogin.login')
        input("\n>>> 로그인 완료 후 Enter 키를 누르세요...")

        # 쿠키 저장
        save_cookies(driver)
        print("\n쿠키가 저장되었습니다!")
        print("이제 자동 모드로 크롤링할 수 있습니다.")

    finally:
        driver.quit()


def auto_crawl(product_url):
    """자동 크롤링 모드 - 저장된 쿠키 사용"""
    print("=" * 60)
    print("자동 크롤링 모드")
    print("=" * 60)

    if not os.path.exists(COOKIE_FILE):
        print("저장된 쿠키가 없습니다!")
        print("먼저 'python cookie_crawler.py login' 을 실행하세요.")
        return

    options = uc.ChromeOptions()
    options.add_argument("--lang=ko-KR")
    driver = uc.Chrome(options=options, version_main=143)

    try:
        # 쿠키 로드
        load_cookies(driver)

        # 상품 페이지 접근
        print(f"\n상품 페이지 접근: {product_url}")

        # CAPTCHA 해결 루프
        for attempt in range(5):
            driver.get(product_url)
            time.sleep(3)

            page_source = driver.page_source or ""
            if '보안 확인' in page_source:
                print(f"   [CAPTCHA {attempt+1}] 해결 시도...")
                driver.save_screenshot(f'/tmp/captcha_page_{attempt+1}.png')
                solved = solve_captcha(driver)
                if not solved:
                    print("   자동 해결 실패 - 30초 대기 (수동 입력)")
                    time.sleep(30)
                continue

            # CAPTCHA 없으면 성공
            if driver.title and 'smartstore' in driver.current_url:
                print(f"   페이지 제목: {driver.title}")
                break

        # 스크롤
        driver.execute_script("window.scrollTo(0, 2000)")
        time.sleep(2)

        # 판매자 상세정보 버튼 찾기
        print("\n판매자 상세정보 버튼 클릭...")
        try:
            # 여러 셀렉터 시도
            btn = None
            selectors = [
                "//button[contains(text(), '판매자 상세정보')]",
                "//button[contains(text(), '판매자 상세정보 확인')]",
                "//button[contains(@class, 'seller')]",
                "//*[contains(text(), '판매자 상세정보')]",
            ]
            for sel in selectors:
                try:
                    btn = driver.find_element(By.XPATH, sel)
                    if btn and btn.is_displayed():
                        print(f"   버튼 발견: {sel}")
                        break
                except:
                    continue

            if btn:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                time.sleep(2)

                # 버튼 직접 클릭
                print("   버튼 클릭...")
                btn.click()
                time.sleep(3)
                print("   ✅ 클릭 완료!")

                # 이미지 수집 모드 - Q 누를때까지 계속
                print("\n   === 이미지 수집 모드 ===")
                print("   C: 캡쳐 / R: 새로고침 / Q: 종료")
                print("   (키만 누르세요, Enter 불필요)")

                while True:
                    try:
                        cmd = getch().lower()
                        print(f"   [입력: {repr(cmd)}]")

                        if cmd == 'c':
                            existing = [f for f in os.listdir(CAPTCHA_DATASET_DIR) if f.endswith('.png')]
                            next_num = len(existing) + 1
                            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                            filename = f"captcha_{next_num:04d}_{timestamp}.png"
                            filepath = os.path.join(CAPTCHA_DATASET_DIR, filename)
                            driver.save_screenshot(filepath)
                            print(f"   ✅ 저장: {filename} (총 {next_num}개)")
                        elif cmd == 'r':
                            print("   새로고침 중...")
                            driver.refresh()
                            time.sleep(3)
                            try:
                                btn = driver.find_element(By.XPATH, "//*[contains(text(), '판매자 상세정보')]")
                                btn.click()
                                time.sleep(2)
                                print("   ✅ 버튼 재클릭 완료!")
                            except:
                                print("   버튼 재클릭 실패 - 수동으로 클릭하세요")
                        elif cmd == 'q':
                            total = len([f for f in os.listdir(CAPTCHA_DATASET_DIR) if f.endswith('.png')])
                            print(f"\n   총 저장: {total}개")
                            driver.quit()
                            return None
                        elif cmd == '\x03':  # Ctrl+C
                            print("\n   Ctrl+C 감지 - 종료")
                            driver.quit()
                            return None
                        # 다른 입력은 무시하고 계속
                    except Exception as e:
                        print(f"   에러: {e}")
                        continue

                # 아래는 실행 안됨
                time.sleep(2)

                # 새 창 확인
                windows = driver.window_handles
                print(f"   열린 창 수: {len(windows)}")
                if len(windows) > 1:
                    driver.switch_to.window(windows[-1])
                    print("   새 창으로 전환!")
                    time.sleep(2)

                # iframe 확인 및 전환
                iframes = driver.find_elements(By.TAG_NAME, 'iframe')
                print(f"   iframe 수: {len(iframes)}")
                for i, iframe in enumerate(iframes):
                    try:
                        if iframe.is_displayed():
                            driver.switch_to.frame(iframe)
                            ps = driver.page_source or ""
                            if '영수증' in ps or '정답' in ps or '판매자 정보' in ps:
                                print(f"   iframe {i}로 전환 (CAPTCHA 발견)!")
                                break
                            driver.switch_to.default_content()
                    except:
                        driver.switch_to.default_content()

                # 클릭 후 스크린샷
                driver.save_screenshot('/tmp/after_click.png')
                print("   스크린샷: /tmp/after_click.png")
            else:
                print("   버튼을 찾지 못함")

            # 로그인 알림창 처리
            try:
                alert = driver.switch_to.alert
                alert_text = alert.text
                print(f"   알림창: {alert_text}")
                if '로그인' in alert_text:
                    alert.accept()  # "확인" 클릭
                    print("   로그인 필요 - 로그인 페이지로 이동 중...")
                    time.sleep(2)
                    # 로그인 후 다시 시도 필요
                    print("   ⚠️ 쿠키가 만료되었습니다. 다시 로그인해주세요:")
                    print("   python3 cookie_crawler.py login")
                    return
                else:
                    alert.dismiss()
            except:
                pass  # 알림창 없음

            time.sleep(3)
        except Exception as e:
            print(f"   버튼 못 찾음: {e}")

        # 판매자 정보 CAPTCHA 해결 루프
        print("\nCAPTCHA 감지 중...")
        for attempt in range(10):
            # 알림창 먼저 처리
            try:
                alert = driver.switch_to.alert
                alert.accept()
                time.sleep(1)
            except:
                pass

            page_source = driver.page_source or ""

            # 디버그: 페이지 소스 일부 출력
            if attempt == 0:
                print(f"   페이지 소스 길이: {len(page_source)}")
                # CAPTCHA 관련 키워드 검색
                keywords = ['영수증', '인증', 'CAPTCHA', '정답', '입력', '확인', '총', '금액', '전화번호']
                found_kw = [kw for kw in keywords if kw in page_source]
                print(f"   발견된 키워드: {found_kw}")

            # 실제 CAPTCHA 질문 패턴 확인 (더 구체적으로)
            is_captcha = False
            if '영수증에서' in page_source or '인증 절차' in page_source:
                is_captcha = True
            elif '번째 숫자는 무엇입니까' in page_source:
                is_captcha = True
            elif '빈 칸에 들어갈' in page_source:
                is_captcha = True
            elif '총 구매 금액' in page_source or '총 금액' in page_source:
                is_captcha = True
            elif '판매자 정보 확인' in page_source and '정답을 입력' in page_source:
                is_captcha = True
            # 추가 패턴
            elif '정답을 입력' in page_source:
                is_captcha = True
            elif '확인하기' in page_source and '영수증' in page_source:
                is_captcha = True

            if is_captcha:
                print(f"\n   [판매자 CAPTCHA {attempt+1}] 감지!")
                print("   ----------------------------------------")
                print("   C: 이미지 저장 (데이터 수집)")
                print("   S: CAPTCHA 풀기 시도")
                print("   R: 새로고침")
                print("   Q: 종료")
                print("   ----------------------------------------")

                user_input = input("   >> ").strip().lower()

                if user_input == 'c':
                    # 이미지 저장
                    existing = [f for f in os.listdir(CAPTCHA_DATASET_DIR) if f.endswith('.png')]
                    next_num = len(existing) + 1
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"captcha_{next_num:04d}_{timestamp}.png"
                    filepath = os.path.join(CAPTCHA_DATASET_DIR, filename)
                    driver.save_screenshot(filepath)
                    print(f"   ✅ 저장: {filename} (총 {next_num}개)")
                    continue
                elif user_input == 's':
                    # 기존 방식으로 풀기
                    driver.save_screenshot(f'/tmp/seller_captcha_{attempt+1}.png')
                    solved = solve_captcha(driver)
                    if not solved:
                        print("   자동 해결 실패")
                        print("   >>> 수동으로 CAPTCHA를 풀고 30초 대기...")
                        time.sleep(30)
                    time.sleep(2)
                    continue
                elif user_input == 'q':
                    print("   종료!")
                    return None
                else:  # r 또는 기타
                    continue

            # CAPTCHA 없으면 종료
            break

        # 결과 추출
        print("\n결과 추출...")
        page_source = driver.page_source or ""
        driver.save_screenshot('/tmp/result.png')

        # 전화번호 추출 (한국 전화번호 형식 - 정확한 지역번호만)
        # 02: 서울 (특수 - 2자리)
        # 031-033: 경기, 강원
        # 041-044: 충청
        # 051-055: 부산, 울산, 경상
        # 061-064: 광주, 전라, 제주
        # 010, 011: 휴대폰
        # 070: 인터넷전화
        valid_area_codes = r'0(?:2|3[1-3]|4[1-4]|5[1-5]|6[1-4]|70|10|11)'
        phone_patterns = [
            # "전화번호" 라벨 근처 (하이픈 필수)
            rf'전화번호[^0-9]*({valid_area_codes})-(\d{{3,4}})-(\d{{4}})',
            rf'연락처[^0-9]*({valid_area_codes})-(\d{{3,4}})-(\d{{4}})',
            # 일반 한국 전화번호 패턴 (하이픈 필수)
            rf'({valid_area_codes})-(\d{{3,4}})-(\d{{4}})',
        ]

        found_phones = set()
        for pat in phone_patterns:
            matches = re.findall(pat, page_source)
            for match in matches:
                if isinstance(match, tuple):
                    phone = f"{match[0]}-{match[1]}-{match[2]}"
                else:
                    phone = match
                # 대표번호 제외 (1588, 1544 등)
                if '1588' not in phone and '1544' not in phone and '1577' not in phone:
                    # 네이버 번호 제외
                    if phone not in ['1588-3819']:
                        # 두번째, 세번째 부분 길이 확인
                        parts = phone.split('-')
                        if len(parts) == 3:
                            # 첫번째 부분이 유효한 지역번호인지 확인
                            first = parts[0]
                            # 02는 특별히 처리
                            if first == '02' or (len(first) == 3 and first[0] == '0'):
                                # 두번째 부분은 3-4자리
                                if 3 <= len(parts[1]) <= 4:
                                    # 세번째 부분은 4자리
                                    if len(parts[2]) == 4:
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
            match = re.search(pat, page_source)
            if match:
                val = match.group(1).strip()
                if '220-81-62517' not in val and '최수연' not in val:
                    print(f"   {name}: {val}")

        print(f"\n스크린샷: /tmp/result.png")

        # 쿠키 갱신 저장
        save_cookies(driver)

        print("\n60초 대기 (브라우저 확인)...")
        time.sleep(60)

    finally:
        driver.quit()


def test_ocr(image_path=None):
    """OCR 테이블 파싱 테스트"""
    if image_path is None:
        # 기본 테스트 이미지
        candidates = [
            '/tmp/captcha_img.png',
            '/tmp/seller_captcha_1.png',
            '/tmp/captcha_page_1.png',
        ]
        for path in candidates:
            if os.path.exists(path):
                image_path = path
                break

    if not image_path or not os.path.exists(image_path):
        print("테스트할 이미지가 없습니다.")
        print("먼저 크롤러를 실행하여 CAPTCHA 스크린샷을 생성하세요.")
        return

    print(f"테스트 이미지: {image_path}")
    print("=" * 60)

    # OCR 초기화
    reader = get_ocr()

    # 원본 OCR
    print("\n[1] 원본 이미지 OCR (PaddleOCR)")
    paddle_result1 = reader.predict(image_path)
    result1 = paddle_to_easyocr_format(paddle_result1)
    if result1:
        print(f"   감지된 텍스트 수: {len(result1)}")
        for i, line in enumerate(result1):
            bbox = line[0]
            text = line[1]
            conf = line[2]
            center_x = (bbox[0][0] + bbox[2][0]) / 2
            center_y = (bbox[0][1] + bbox[2][1]) / 2
            print(f"   [{i+1}] ({center_x:.0f}, {center_y:.0f}) conf={conf:.2f}: {text}")

    # 전처리 후 OCR
    print("\n[2] 전처리 이미지 OCR (PaddleOCR)")
    processed = preprocess_image(image_path)
    paddle_result2 = reader.predict(processed)
    result2 = paddle_to_easyocr_format(paddle_result2)
    if result2:
        print(f"   감지된 텍스트 수: {len(result2)}")
        for i, line in enumerate(result2):
            bbox = line[0]
            text = line[1]
            conf = line[2]
            center_x = (bbox[0][0] + bbox[2][0]) / 2
            center_y = (bbox[0][1] + bbox[2][1]) / 2
            print(f"   [{i+1}] ({center_x:.0f}, {center_y:.0f}) conf={conf:.2f}: {text}")

    # 테이블 파싱 테스트
    print("\n[3] 테이블 파싱 테스트")
    table_result = parse_receipt_table(result1)
    if table_result:
        print(f"   단가: {table_result['단가']}")
        print(f"   수량: {table_result['수량']}")
        print(f"   합계: {table_result['합계']}")
        print(f"   총 구매 금액: {table_result['total']}")
        print(f"   총 개수: {table_result.get('item_count', 0)}")
    else:
        print("   테이블 파싱 실패")

    print("\n" + "=" * 60)


def main():
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == 'login':
        manual_login()
    elif len(sys.argv) > 1 and sys.argv[1] == 'test':
        # OCR 테스트 모드
        image_path = sys.argv[2] if len(sys.argv) > 2 else None
        test_ocr(image_path)
    else:
        # 기본 상품 URL
        url = "https://smartstore.naver.com/main/products/7255034137"
        if len(sys.argv) > 1:
            url = sys.argv[1]
        auto_crawl(url)


if __name__ == '__main__':
    main()
