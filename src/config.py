"""설정 관리 모듈"""
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()


class Config:
    """환경 변수 기반 설정"""

    # 데이터베이스 연결 문자열
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///history.db")

    # Google AI API 키 (Gemini)
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")


config = Config()
