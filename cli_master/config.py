"""설정 관리 모듈"""

import os
from pathlib import Path

from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()


def _ensure_parent_dir(db_path: Path) -> None:
    """DB 파일이 저장될 상위 폴더를 보장"""
    db_path.parent.mkdir(parents=True, exist_ok=True)


class Config:
    """환경 변수 기반 설정"""

    def __init__(self) -> None:
        self.PROJECT_ROOT = Path(__file__).resolve().parent.parent
        self.DB_DIR = Path(os.getenv("DATABASE_DIR", str(self.PROJECT_ROOT / "db")))
        self.HISTORY_DB_PATH = Path(
            os.getenv("HISTORY_DB_PATH", str(self.DB_DIR / "history.db"))
        )
        self.CHECKPOINT_DB_PATH = Path(
            os.getenv("CHECKPOINT_DB_PATH", str(self.DB_DIR / "checkpoints.db"))
        )

        _ensure_parent_dir(self.HISTORY_DB_PATH)
        _ensure_parent_dir(self.CHECKPOINT_DB_PATH)

        # 데이터베이스 연결 문자열
        self.DATABASE_URL = os.getenv(
            "DATABASE_URL", f"sqlite:///{self.HISTORY_DB_PATH}"
        )

        # AI 모델 설정
        self.MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.5-flash")
        self.MODEL_TEMPERATURE = float(os.getenv("MODEL_TEMPERATURE", "0.7"))
        # 테스트용 가짜 LLM 모드
        self.FAKE_LLM = os.getenv("CLI_MASTER_FAKE_LLM", "0") == "1"


config = Config()
