"""설정 관리 모듈"""
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()


class Config:
    """환경 변수 기반 설정"""

    # 데이터베이스 연결 문자열
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///history.db")

    # AI 모델 설정
    MODEL_NAME: str = os.getenv("MODEL_NAME", "gemini-2.5-flash")
    MODEL_TEMPERATURE: float = float(os.getenv("MODEL_TEMPERATURE", "0.7"))


config = Config()
