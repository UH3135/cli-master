"""설정 관리 모듈"""

import os
from pathlib import Path

from dotenv import load_dotenv

from .safe_path import FileAccessPolicy

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

        # LangGraph 설정
        self.DEFAULT_RECURSION_LIMIT = int(os.getenv("RECURSION_LIMIT", "25"))
        self.RESEARCH_RECURSION_LIMIT = int(os.getenv("RESEARCH_RECURSION_LIMIT", "50"))

        # 파일 접근 정책
        self.FILE_ACCESS_POLICY = self._build_file_access_policy()

    def _build_file_access_policy(self) -> FileAccessPolicy:
        """환경 변수 기반 파일 접근 정책 생성"""
        policy = FileAccessPolicy.default(working_dir=self.PROJECT_ROOT)

        # 환경 변수로 추가 읽기 허용 경로 설정
        # 예: ALLOWED_READ_PATHS=/home/user/docs:/home/user/projects
        extra_read_paths = os.getenv("ALLOWED_READ_PATHS", "")
        if extra_read_paths:
            for path_str in extra_read_paths.split(":"):
                if path_str.strip():
                    policy.allowed_read_paths.append(Path(path_str.strip()))

        # 환경 변수로 추가 쓰기 허용 경로 설정
        # 예: ALLOWED_WRITE_PATHS=/home/user/output
        extra_write_paths = os.getenv("ALLOWED_WRITE_PATHS", "")
        if extra_write_paths:
            for path_str in extra_write_paths.split(":"):
                if path_str.strip():
                    policy.allowed_write_paths.append(Path(path_str.strip()))

        # 추가 블랙리스트 경로
        # 예: BLACKLISTED_PATHS=/sensitive/data
        extra_blacklist = os.getenv("BLACKLISTED_PATHS", "")
        if extra_blacklist:
            for path_str in extra_blacklist.split(":"):
                if path_str.strip():
                    policy.blacklisted_paths.append(Path(path_str.strip()))

        return policy


config = Config()
