import os
from dotenv import load_dotenv

load_dotenv()

# 네이버 API 설정
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")

# 데이터베이스 설정
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data.db")

# 크롤링 설정
CRAWL_DELAY = float(os.getenv("CRAWL_DELAY", "1.5"))
MAX_CONCURRENT_CRAWL = int(os.getenv("MAX_CONCURRENT_CRAWL", "3"))

# 공정거래위원회 API 설정 (통신판매사업자 조회)
FTC_API_KEY = os.getenv("FTC_API_KEY", "")

# 카카오 REST API 설정 (로컬 검색)
KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY", "")
