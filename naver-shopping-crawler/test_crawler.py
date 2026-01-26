"""
크롤러 테스트 스크립트

사용법:
1. python3 test_crawler.py 실행
2. 브라우저에서 네이버 로그인
3. 로그인 완료 후 자동으로 전화번호 추출 테스트
"""
import asyncio
import sys
sys.path.insert(0, '.')

from app.services.crawler import phone_crawler


async def test():
    print("=" * 60)
    print("스마트스토어 전화번호 크롤러 테스트")
    print("=" * 60)
    print("\n⚠️  전화번호 확인에는 네이버 로그인이 필요합니다.")
    print("    브라우저가 열리면 네이버에 로그인해주세요.\n")

    # 테스트할 URL (DB에서 가져온 실제 상품)
    test_url = "https://smartstore.naver.com/main/products/7255034137"
    store_name = "제이X제곱"

    print(f"테스트 URL: {test_url}")
    print(f"스토어명: {store_name}")
    print("-" * 60)

    try:
        phone = await phone_crawler.get_phone_number(test_url, store_name)

        if phone:
            print(f"\n✅ 전화번호 추출 성공: {phone}")
        else:
            print("\n❌ 전화번호를 추출하지 못했습니다.")
            print("   - 네이버 로그인이 되어있는지 확인해주세요.")
            print("   - 상품이 운영 중지 상태일 수 있습니다.")

    except Exception as e:
        print(f"\n오류 발생: {e}")

    finally:
        await phone_crawler.close_browser()

    print("\n테스트 완료!")


if __name__ == '__main__':
    asyncio.run(test())
