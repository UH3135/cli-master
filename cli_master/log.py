"""로깅 설정 모듈"""

from pathlib import Path

from loguru import logger


def setup_logging() -> None:
    """UI와 분리된 실행 로그를 파일로 저장"""
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "runtime.log"

    # 기본 stderr 핸들러 제거 (콘솔 출력 방지)
    logger.remove()

    # 파일 핸들러 추가 (rotation, retention 자동 지원)
    logger.add(
        log_path,
        format="{time:YYYY-MM-DD HH:mm:ss} {level} {name}: {message}",
        level="INFO",
        rotation="5 MB",
        retention=5,
        encoding="utf-8",
    )
