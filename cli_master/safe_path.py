"""안전한 파일 경로 검증 모듈

계층형 권한 시스템:
- READ: 가장 넓은 권한 (블랙리스트만 차단)
- WRITE: 화이트리스트 내에서만 허용
- DELETE: 가장 제한적 (화이트리스트 + 확인 필요)
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from loguru import logger


class OperationType(Enum):
    """파일 작업 유형"""

    READ = "read"  # 가장 넓은 권한
    WRITE = "write"  # 중간 권한
    DELETE = "delete"  # 가장 제한적


@dataclass
class PathValidationResult:
    """경로 검증 결과"""

    allowed: bool
    reason: str
    normalized_path: Path | None = None


@dataclass
class FileAccessPolicy:
    """파일 접근 정책 설정

    Attributes:
        allowed_read_paths: 읽기 허용 경로 목록 (비어있으면 블랙리스트만 적용)
        allowed_write_paths: 쓰기 허용 경로 목록 (필수)
        blacklisted_paths: 절대 접근 불가 경로 (모든 작업에 적용)
        blacklisted_patterns: 차단할 파일 패턴 (예: .env, *.key)
        allow_absolute_paths: 절대 경로 허용 여부
        require_confirmation_for_delete: 삭제 시 확인 필요 여부
    """

    allowed_read_paths: list[Path] = field(default_factory=list)
    allowed_write_paths: list[Path] = field(default_factory=list)
    blacklisted_paths: list[Path] = field(default_factory=list)
    blacklisted_patterns: list[str] = field(default_factory=list)
    allow_absolute_paths: bool = True
    require_confirmation_for_delete: bool = True

    @classmethod
    def default(cls, working_dir: Path | None = None) -> "FileAccessPolicy":
        """기본 정책 생성

        - 읽기: 블랙리스트 외 모든 경로 허용
        - 쓰기: 작업 디렉토리 하위만 허용
        - 삭제: 작업 디렉토리 하위만 + 확인 필요
        """
        if working_dir is None:
            working_dir = Path.cwd()

        return cls(
            allowed_read_paths=[],  # 비어있으면 블랙리스트만 적용 (넓은 읽기 권한)
            allowed_write_paths=[working_dir],
            blacklisted_paths=cls._default_blacklist(),
            blacklisted_patterns=cls._default_blacklist_patterns(),
            allow_absolute_paths=True,
            require_confirmation_for_delete=True,
        )

    @staticmethod
    def _default_blacklist() -> list[Path]:
        """기본 블랙리스트 경로"""
        home = Path.home()
        return [
            # 시스템 중요 경로
            Path("/etc"),
            Path("/boot"),
            Path("/sys"),
            Path("/proc"),
            Path("/dev"),
            Path("/root"),
            Path("/var/log"),
            # 사용자 민감 경로
            home / ".ssh",
            home / ".gnupg",
            home / ".aws",
            home / ".config",
            home / ".local/share/keyrings",
            # 패키지 관리자
            Path("/usr"),
            Path("/bin"),
            Path("/sbin"),
        ]

    @staticmethod
    def _default_blacklist_patterns() -> list[str]:
        """기본 블랙리스트 파일 패턴"""
        return [
            ".env",
            ".env.*",
            "*.pem",
            "*.key",
            "*.crt",
            "id_rsa",
            "id_rsa.pub",
            "id_ed25519",
            "id_ed25519.pub",
            "*.sqlite",
            "*.db",
            "credentials.json",
            "token.json",
            ".netrc",
            ".npmrc",
            ".pypirc",
        ]


class SafePathValidator:
    """안전한 경로 검증기

    사용 예시:
        validator = SafePathValidator(policy)
        result = validator.validate("/some/path", OperationType.READ)
        if result.allowed:
            # 안전하게 파일 접근
            pass
        else:
            print(f"접근 거부: {result.reason}")
    """

    def __init__(self, policy: FileAccessPolicy):
        self.policy = policy

    def validate(
        self, path: str | Path, operation: OperationType
    ) -> PathValidationResult:
        """경로와 작업 유형에 따른 접근 권한 검증

        Args:
            path: 검증할 경로
            operation: 작업 유형 (READ/WRITE/DELETE)

        Returns:
            PathValidationResult: 검증 결과
        """
        try:
            # 1. 경로 정규화 (path traversal 방지)
            normalized = self._normalize_path(path)
        except ValueError as e:
            return PathValidationResult(
                allowed=False, reason=f"경로 정규화 실패: {e}"
            )

        # 2. 절대 경로 체크
        if not self.policy.allow_absolute_paths and normalized.is_absolute():
            if not self._is_under_allowed_paths(normalized, operation):
                return PathValidationResult(
                    allowed=False,
                    reason="절대 경로는 허용되지 않습니다",
                    normalized_path=normalized,
                )

        # 3. 블랙리스트 체크 (모든 작업에 적용)
        blacklist_check = self._check_blacklist(normalized)
        if not blacklist_check.allowed:
            return blacklist_check

        # 4. 작업 유형별 권한 체크
        if operation == OperationType.READ:
            return self._validate_read(normalized)
        elif operation == OperationType.WRITE:
            return self._validate_write(normalized)
        else:  # DELETE
            return self._validate_delete(normalized)

    def _normalize_path(self, path: str | Path) -> Path:
        """경로 정규화 (path traversal 방지)

        - 상대 경로를 절대 경로로 변환
        - symlink 해석
        - '..' 등 정규화
        """
        path = Path(path)

        # 상대 경로는 현재 디렉토리 기준으로 변환
        if not path.is_absolute():
            path = Path.cwd() / path

        # resolve()로 정규화 (.., symlink 해석)
        # strict=False: 존재하지 않는 경로도 정규화
        try:
            normalized = path.resolve()
        except (OSError, RuntimeError) as e:
            raise ValueError(f"경로 해석 실패: {e}")

        return normalized

    def _check_blacklist(self, path: Path) -> PathValidationResult:
        """블랙리스트 경로 체크"""
        # 경로 블랙리스트 체크
        for blocked in self.policy.blacklisted_paths:
            try:
                blocked_resolved = blocked.resolve()
                # 블랙리스트 경로이거나 그 하위 경로인 경우
                if path == blocked_resolved or self._is_subpath(
                    path, blocked_resolved
                ):
                    logger.warning("블랙리스트 경로 접근 시도: %s", path)
                    return PathValidationResult(
                        allowed=False,
                        reason=f"보안상 접근이 차단된 경로입니다: {blocked}",
                        normalized_path=path,
                    )
            except (OSError, RuntimeError):
                continue

        # 파일명 패턴 블랙리스트 체크
        filename = path.name
        for pattern in self.policy.blacklisted_patterns:
            if self._match_pattern(filename, pattern):
                logger.warning("블랙리스트 패턴 매칭: %s (패턴: %s)", filename, pattern)
                return PathValidationResult(
                    allowed=False,
                    reason=f"보안상 접근이 차단된 파일 유형입니다: {pattern}",
                    normalized_path=path,
                )

        return PathValidationResult(allowed=True, reason="", normalized_path=path)

    def _validate_read(self, path: Path) -> PathValidationResult:
        """읽기 권한 검증

        allowed_read_paths가 비어있으면 블랙리스트만 적용 (넓은 권한)
        """
        # 읽기 허용 목록이 비어있으면 블랙리스트만 적용 (이미 통과)
        if not self.policy.allowed_read_paths:
            return PathValidationResult(
                allowed=True, reason="읽기 허용", normalized_path=path
            )

        # 허용 목록이 있으면 그 안에 있는지 확인
        if self._is_under_allowed_paths(path, OperationType.READ):
            return PathValidationResult(
                allowed=True, reason="읽기 허용", normalized_path=path
            )

        return PathValidationResult(
            allowed=False,
            reason="읽기 허용 경로 외부입니다",
            normalized_path=path,
        )

    def _validate_write(self, path: Path) -> PathValidationResult:
        """쓰기 권한 검증

        반드시 allowed_write_paths 내에 있어야 함
        """
        if not self.policy.allowed_write_paths:
            return PathValidationResult(
                allowed=False,
                reason="쓰기 허용 경로가 설정되지 않았습니다",
                normalized_path=path,
            )

        if self._is_under_allowed_paths(path, OperationType.WRITE):
            return PathValidationResult(
                allowed=True, reason="쓰기 허용", normalized_path=path
            )

        return PathValidationResult(
            allowed=False,
            reason="쓰기 허용 경로 외부입니다. 허용된 경로: "
            + ", ".join(str(p) for p in self.policy.allowed_write_paths),
            normalized_path=path,
        )

    def _validate_delete(self, path: Path) -> PathValidationResult:
        """삭제 권한 검증

        쓰기 권한과 동일 + 추가 확인 필요
        """
        # 먼저 쓰기 권한 체크 (삭제는 쓰기 권한 필요)
        write_result = self._validate_write(path)
        if not write_result.allowed:
            return PathValidationResult(
                allowed=False,
                reason=f"삭제 권한 없음: {write_result.reason}",
                normalized_path=path,
            )

        # 추가 확인 필요 플래그
        if self.policy.require_confirmation_for_delete:
            return PathValidationResult(
                allowed=True,
                reason="삭제 허용 (확인 필요)",
                normalized_path=path,
            )

        return PathValidationResult(
            allowed=True, reason="삭제 허용", normalized_path=path
        )

    def _is_under_allowed_paths(self, path: Path, operation: OperationType) -> bool:
        """경로가 허용된 경로 하위에 있는지 확인"""
        if operation == OperationType.READ:
            allowed_paths = self.policy.allowed_read_paths
        else:  # WRITE, DELETE
            allowed_paths = self.policy.allowed_write_paths

        for allowed in allowed_paths:
            try:
                allowed_resolved = allowed.resolve()
                if path == allowed_resolved or self._is_subpath(path, allowed_resolved):
                    return True
            except (OSError, RuntimeError):
                continue

        return False

    @staticmethod
    def _is_subpath(path: Path, parent: Path) -> bool:
        """path가 parent의 하위 경로인지 확인"""
        try:
            path.relative_to(parent)
            return True
        except ValueError:
            return False

    @staticmethod
    def _match_pattern(filename: str, pattern: str) -> bool:
        """간단한 패턴 매칭 (glob 스타일)"""
        import fnmatch

        return fnmatch.fnmatch(filename, pattern)


# 전역 싱글톤
_validator: SafePathValidator | None = None


def get_validator(policy: FileAccessPolicy | None = None) -> SafePathValidator:
    """전역 검증기 반환 (싱글톤)"""
    global _validator
    if _validator is None:
        if policy is None:
            policy = FileAccessPolicy.default()
        _validator = SafePathValidator(policy)
    return _validator


def reset_validator() -> None:
    """검증기 초기화 (테스트용)"""
    global _validator
    _validator = None


def validate_path(
    path: str | Path, operation: OperationType
) -> PathValidationResult:
    """경로 검증 단축 함수"""
    return get_validator().validate(path, operation)
