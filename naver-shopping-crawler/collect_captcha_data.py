"""
CAPTCHA 데이터 수집 스크립트
- 크롤러 실행 중 CAPTCHA 이미지 저장
- 수동으로 정답 입력
- 파인튜닝용 데이터셋 구축
"""
import json
import os
import time
import shutil
from datetime import datetime
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 데이터셋 폴더
DATASET_DIR = '/Users/teramime/Documents/project_20/naver-shopping-crawler/captcha_dataset'
METADATA_FILE = os.path.join(DATASET_DIR, 'metadata.json')


def load_metadata():
    """메타데이터 로드"""
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'total_count': 0, 'data': []}


def save_metadata(metadata):
    """메타데이터 저장"""
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)


def get_next_id(metadata):
    """다음 ID 생성"""
    return metadata['total_count'] + 1


def save_captcha_data(image_path, question, answer, metadata):
    """CAPTCHA 데이터 저장"""
    captcha_id = get_next_id(metadata)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # 파일명 생성
    filename = f"captcha_{captcha_id:04d}_{timestamp}"

    # 이미지 복사
    new_image_path = os.path.join(DATASET_DIR, f"{filename}.png")
    shutil.copy(image_path, new_image_path)

    # 개별 JSON 저장
    json_path = os.path.join(DATASET_DIR, f"{filename}.json")
    data = {
        'id': captcha_id,
        'image': f"{filename}.png",
        'question': question,
        'answer': answer,
        'timestamp': timestamp
    }
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 메타데이터 업데이트
    metadata['total_count'] = captcha_id
    metadata['data'].append(data)
    save_metadata(metadata)

    print(f"\n   ✅ 저장 완료: {filename}")
    print(f"   총 수집 데이터: {captcha_id}개")

    return captcha_id


def collect_from_crawler():
    """크롤러에서 CAPTCHA 수집"""
    print("=" * 60)
    print("CAPTCHA 데이터 수집 모드")
    print("=" * 60)
    print(f"저장 위치: {DATASET_DIR}")
    print()

    metadata = load_metadata()
    print(f"기존 수집 데이터: {metadata['total_count']}개\n")

    # 브라우저 설정
    options = uc.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    print("[1] 브라우저 시작...")
    driver = uc.Chrome(options=options)

    # 테스트 URL
    test_url = "https://smartstore.naver.com/main/products/7255034137"

    try:
        print(f"[2] 페이지 이동: {test_url}")
        driver.get(test_url)
        time.sleep(3)

        # 판매자 정보 버튼 찾기
        print("[3] '판매자 상세정보' 버튼 찾기...")

        try:
            seller_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "a._26MYJfApxOCz0o0S9g3HtD"))
            )
            seller_btn.click()
            print("   버튼 클릭!")
            time.sleep(2)
        except:
            # 대체 방법
            links = driver.find_elements(By.TAG_NAME, 'a')
            for link in links:
                if '판매자' in (link.text or '') and '상세' in (link.text or ''):
                    link.click()
                    print("   대체 버튼 클릭!")
                    time.sleep(2)
                    break

        # CAPTCHA 수집 루프
        while True:
            print("\n" + "=" * 60)
            print("[CAPTCHA 수집]")
            print("=" * 60)

            # CAPTCHA 이미지 캡처
            captcha_path = '/tmp/captcha_collect.png'
            driver.save_screenshot(captcha_path)
            print(f"   스크린샷 저장: {captcha_path}")

            # 질문 텍스트 추출 시도
            question = ""
            try:
                # CAPTCHA 질문 요소 찾기
                question_elements = driver.find_elements(By.CSS_SELECTOR, '.captcha_question, .question, [class*="question"]')
                for elem in question_elements:
                    if elem.text:
                        question = elem.text
                        break

                if not question:
                    # 페이지 텍스트에서 질문 패턴 찾기
                    page_text = driver.find_element(By.TAG_NAME, 'body').text
                    import re
                    q_match = re.search(r'(총 구매 금액|총 금액|몇 개|몇개|얼마|번째 숫자).+?\?', page_text)
                    if q_match:
                        question = q_match.group(0)
            except:
                pass

            print(f"\n   감지된 질문: {question or '(직접 입력 필요)'}")

            # 사용자 입력
            print("\n   [수동 입력]")

            if not question:
                question = input("   질문 입력 (예: 총 구매 금액은?): ").strip()
            else:
                confirm = input(f"   질문 확인 [{question}] (Enter=확인, 직접입력): ").strip()
                if confirm:
                    question = confirm

            answer = input("   정답 입력 (숫자만): ").strip()

            if answer.lower() == 'q':
                print("\n   수집 종료!")
                break

            if answer.lower() == 's':
                print("   이 CAPTCHA 건너뛰기")
                continue

            if answer.lower() == 'r':
                print("   페이지 새로고침...")
                driver.refresh()
                time.sleep(3)
                continue

            # 데이터 저장
            try:
                answer_int = int(answer)
                save_captcha_data(captcha_path, question, answer_int, metadata)
            except ValueError:
                print("   ⚠️ 숫자만 입력해주세요!")
                continue

            # 다음 동작
            print("\n   [다음 동작]")
            print("   Enter: 새 CAPTCHA 캡처")
            print("   r: 페이지 새로고침")
            print("   n: 새 상품 페이지로 이동")
            print("   q: 종료")

            action = input("   선택: ").strip().lower()

            if action == 'q':
                break
            elif action == 'r':
                driver.refresh()
                time.sleep(3)
            elif action == 'n':
                new_url = input("   새 상품 URL: ").strip()
                if new_url:
                    driver.get(new_url)
                    time.sleep(3)

    except KeyboardInterrupt:
        print("\n\n중단됨!")

    finally:
        print(f"\n최종 수집 데이터: {metadata['total_count']}개")
        driver.quit()


def collect_from_existing_images():
    """기존 이미지에서 데이터 수집 (수동 라벨링)"""
    print("=" * 60)
    print("기존 이미지 라벨링 모드")
    print("=" * 60)

    metadata = load_metadata()
    print(f"기존 수집 데이터: {metadata['total_count']}개\n")

    # /tmp에서 captcha 이미지 찾기
    import glob
    images = glob.glob('/tmp/captcha*.png')

    if not images:
        print("라벨링할 이미지가 없습니다.")
        print("이미지 경로를 직접 입력하세요.")
        image_path = input("이미지 경로: ").strip()
        if not os.path.exists(image_path):
            print("파일이 존재하지 않습니다.")
            return
        images = [image_path]

    print(f"발견된 이미지: {len(images)}개\n")

    for img_path in images:
        print(f"\n이미지: {img_path}")
        print("(이미지를 직접 확인하세요)")

        question = input("질문 입력 (q=종료, s=건너뛰기): ").strip()

        if question.lower() == 'q':
            break
        if question.lower() == 's':
            continue

        answer = input("정답 입력 (숫자만): ").strip()

        try:
            answer_int = int(answer)
            save_captcha_data(img_path, question, answer_int, metadata)
        except ValueError:
            print("⚠️ 숫자만 입력해주세요!")
            continue

    print(f"\n최종 수집 데이터: {metadata['total_count']}개")


def view_dataset():
    """수집된 데이터셋 확인"""
    metadata = load_metadata()

    print("=" * 60)
    print("수집된 데이터셋")
    print("=" * 60)
    print(f"총 수집: {metadata['total_count']}개\n")

    for item in metadata['data'][-10:]:  # 최근 10개만 표시
        print(f"  ID: {item['id']}")
        print(f"  질문: {item['question']}")
        print(f"  정답: {item['answer']}")
        print(f"  이미지: {item['image']}")
        print()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("CAPTCHA 데이터 수집 도구")
    print("=" * 60)
    print("\n[모드 선택]")
    print("1. 크롤러로 새 CAPTCHA 수집")
    print("2. 기존 이미지 라벨링")
    print("3. 수집된 데이터셋 확인")
    print("q. 종료")

    choice = input("\n선택: ").strip()

    if choice == '1':
        collect_from_crawler()
    elif choice == '2':
        collect_from_existing_images()
    elif choice == '3':
        view_dataset()
    else:
        print("종료")
