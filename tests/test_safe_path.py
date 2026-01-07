"""SafePathValidator 테스트"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from cli_master.core.safe_path import (
    FileAccessPolicy,
    OperationType,
    PathValidationResult,
    SafePathValidator,
    get_validator,
    reset_validator,
    validate_path,
)


@pytest.fixture(autouse=True)
def reset_global_validator():
    """각 테스트 전후로 전역 검증기 초기화"""
    reset_validator()
    yield
    reset_validator()


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """테스트용 임시 디렉토리"""
    return tmp_path


@pytest.fixture
def working_dir(temp_dir: Path) -> Path:
    """테스트용 작업 디렉토리"""
    work = temp_dir / "workspace"
    work.mkdir()
    return work


@pytest.fixture
def test_file(working_dir: Path) -> Path:
    """테스트용 파일"""
    file = working_dir / "test.txt"
    file.write_text("test content")
    return file


@pytest.fixture
def policy(working_dir: Path) -> FileAccessPolicy:
    """테스트용 기본 정책"""
    return FileAccessPolicy.default(working_dir=working_dir)


@pytest.fixture
def validator(policy: FileAccessPolicy) -> SafePathValidator:
    """테스트용 검증기"""
    return SafePathValidator(policy)


class TestFileAccessPolicy:
    """FileAccessPolicy 테스트"""

    def test_default_policy_creation(self, working_dir: Path):
        """기본 정책 생성 테스트"""
        policy = FileAccessPolicy.default(working_dir=working_dir)

        assert policy.allowed_read_paths == []  # 비어있으면 블랙리스트만 적용
        assert working_dir in policy.allowed_write_paths
        assert len(policy.blacklisted_paths) > 0
        assert len(policy.blacklisted_patterns) > 0
        assert policy.require_confirmation_for_delete is True

    def test_default_blacklist_contains_sensitive_paths(self):
        """기본 블랙리스트에 민감한 경로 포함 확인"""
        blacklist = FileAccessPolicy._default_blacklist()

        sensitive_paths = [Path("/etc"), Path("/boot"), Path("/root")]
        for path in sensitive_paths:
            assert path in blacklist

    def test_default_blacklist_patterns_contain_sensitive_files(self):
        """기본 블랙리스트 패턴에 민감한 파일 포함 확인"""
        patterns = FileAccessPolicy._default_blacklist_patterns()

        sensitive_patterns = [".env", "*.pem", "*.key", "id_rsa"]
        for pattern in sensitive_patterns:
            assert pattern in patterns


class TestPathNormalization:
    """경로 정규화 테스트"""

    def test_relative_path_converted_to_absolute(self, validator: SafePathValidator):
        """상대 경로가 절대 경로로 변환되는지 확인"""
        normalized = validator._normalize_path("test.txt")

        assert normalized.is_absolute()
        assert normalized.name == "test.txt"

    def test_path_traversal_normalized(
        self, validator: SafePathValidator, working_dir: Path
    ):
        """경로 순회 공격이 정규화되는지 확인"""
        # working_dir/../working_dir/test.txt 같은 경로가 정규화됨
        traversal_path = working_dir / ".." / working_dir.name / "test.txt"
        normalized = validator._normalize_path(str(traversal_path))

        # 정규화 후 중복 ..이 제거됨
        assert ".." not in str(normalized)


class TestBlacklistValidation:
    """블랙리스트 검증 테스트"""

    def test_etc_path_blocked(self, validator: SafePathValidator):
        """/etc 경로 차단 확인"""
        result = validator.validate("/etc/passwd", OperationType.READ)

        assert result.allowed is False
        assert "보안상 접근이 차단된 경로" in result.reason

    def test_ssh_dir_blocked(self, validator: SafePathValidator):
        """~/.ssh 경로 차단 확인"""
        ssh_path = Path.home() / ".ssh" / "id_rsa"
        result = validator.validate(str(ssh_path), OperationType.READ)

        assert result.allowed is False

    def test_env_file_blocked(self, validator: SafePathValidator, working_dir: Path):
        """*.env 파일 차단 확인"""
        env_file = working_dir / ".env"
        result = validator.validate(str(env_file), OperationType.READ)

        assert result.allowed is False
        assert "보안상 접근이 차단된 파일 유형" in result.reason

    def test_pem_file_blocked(self, validator: SafePathValidator, working_dir: Path):
        """*.pem 파일 차단 확인"""
        pem_file = working_dir / "server.pem"
        result = validator.validate(str(pem_file), OperationType.READ)

        assert result.allowed is False

    def test_normal_file_not_blocked(
        self, validator: SafePathValidator, test_file: Path
    ):
        """일반 파일은 차단되지 않음"""
        result = validator.validate(str(test_file), OperationType.READ)

        assert result.allowed is True


class TestReadPermission:
    """읽기 권한 테스트"""

    def test_read_any_path_when_no_whitelist(
        self, validator: SafePathValidator, temp_dir: Path
    ):
        """화이트리스트가 비어있으면 블랙리스트 외 모든 경로 읽기 가능"""
        # temp_dir은 작업 디렉토리 외부지만 읽기 가능
        other_file = temp_dir / "other.txt"
        other_file.write_text("other content")

        result = validator.validate(str(other_file), OperationType.READ)

        assert result.allowed is True

    def test_read_with_whitelist(self, working_dir: Path, temp_dir: Path):
        """읽기 화이트리스트 설정 시 해당 경로만 읽기 가능"""
        policy = FileAccessPolicy(
            allowed_read_paths=[working_dir],
            allowed_write_paths=[working_dir],
            blacklisted_paths=[],
            blacklisted_patterns=[],
        )
        validator = SafePathValidator(policy)

        # 화이트리스트 내부는 읽기 가능
        inside = working_dir / "inside.txt"
        inside.write_text("inside")
        result_inside = validator.validate(str(inside), OperationType.READ)
        assert result_inside.allowed is True

        # 화이트리스트 외부는 읽기 불가
        outside = temp_dir / "outside.txt"
        outside.write_text("outside")
        result_outside = validator.validate(str(outside), OperationType.READ)
        assert result_outside.allowed is False


class TestWritePermission:
    """쓰기 권한 테스트"""

    def test_write_inside_working_dir_allowed(
        self, validator: SafePathValidator, working_dir: Path
    ):
        """작업 디렉토리 내 쓰기 허용"""
        file_path = working_dir / "new_file.txt"
        result = validator.validate(str(file_path), OperationType.WRITE)

        assert result.allowed is True

    def test_write_outside_working_dir_blocked(
        self, validator: SafePathValidator, temp_dir: Path
    ):
        """작업 디렉토리 외부 쓰기 차단"""
        file_path = temp_dir / "outside.txt"
        result = validator.validate(str(file_path), OperationType.WRITE)

        assert result.allowed is False
        assert "쓰기 허용 경로 외부" in result.reason

    def test_write_to_etc_blocked(self, validator: SafePathValidator):
        """/etc에 쓰기 시도 차단"""
        result = validator.validate("/etc/test.txt", OperationType.WRITE)

        assert result.allowed is False


class TestDeletePermission:
    """삭제 권한 테스트"""

    def test_delete_inside_working_dir_allowed_with_confirmation(
        self, validator: SafePathValidator, test_file: Path
    ):
        """작업 디렉토리 내 삭제는 확인 필요"""
        result = validator.validate(str(test_file), OperationType.DELETE)

        assert result.allowed is True
        assert "확인 필요" in result.reason

    def test_delete_outside_working_dir_blocked(
        self, validator: SafePathValidator, temp_dir: Path
    ):
        """작업 디렉토리 외부 삭제 차단"""
        file_path = temp_dir / "outside.txt"
        file_path.write_text("test")

        result = validator.validate(str(file_path), OperationType.DELETE)

        assert result.allowed is False


class TestPathTraversalAttack:
    """경로 순회 공격 방지 테스트"""

    def test_parent_traversal_normalized(
        self, validator: SafePathValidator, working_dir: Path
    ):
        """상위 디렉토리 순회 시도가 정규화됨"""
        # resolve()가 경로를 정규화하여 ..이 제거됨을 확인
        traversal_path = str(working_dir / ".." / working_dir.name / "test.txt")
        normalized = validator._normalize_path(traversal_path)

        # 정규화 후에는 ..이 없어야 함
        assert ".." not in str(normalized)
        # 정규화된 경로는 원래 의도한 경로와 동일
        assert normalized == working_dir / "test.txt"

    def test_etc_traversal_blocked(self, validator: SafePathValidator):
        """절대 경로로 /etc 접근 시도 차단"""
        # 절대 경로로 직접 /etc 접근 시도
        result = validator.validate("/etc/passwd", OperationType.READ)
        assert result.allowed is False

    def test_symlink_attack_blocked(
        self, validator: SafePathValidator, working_dir: Path
    ):
        """심볼릭 링크 공격 방지 (심링크가 블랙리스트를 가리키는 경우)"""
        # 심링크 생성 (OS 권한이 있어야 함)
        try:
            symlink_path = working_dir / "link_to_etc"
            symlink_path.symlink_to("/etc")

            result = validator.validate(str(symlink_path), OperationType.READ)

            # resolve()가 실제 경로를 반환하므로 /etc가 됨 -> 차단
            assert result.allowed is False
        except OSError:
            pytest.skip("심링크 생성 권한 없음")


class TestGlobalValidator:
    """전역 검증기 테스트"""

    def test_get_validator_returns_singleton(self):
        """get_validator가 싱글톤 반환"""
        v1 = get_validator()
        v2 = get_validator()

        assert v1 is v2

    def test_reset_validator_clears_singleton(self):
        """reset_validator가 싱글톤 초기화"""
        v1 = get_validator()
        reset_validator()
        v2 = get_validator()

        assert v1 is not v2

    def test_validate_path_shortcut(self, working_dir: Path):
        """validate_path 단축 함수 테스트"""
        # 커스텀 정책으로 초기화
        policy = FileAccessPolicy.default(working_dir=working_dir)
        get_validator(policy)

        # 단축 함수 사용
        result = validate_path("/etc/passwd", OperationType.READ)

        assert result.allowed is False


class TestPatternMatching:
    """패턴 매칭 테스트"""

    def test_wildcard_pattern(self, validator: SafePathValidator):
        """와일드카드 패턴 매칭"""
        assert validator._match_pattern("server.key", "*.key") is True
        assert validator._match_pattern("server.txt", "*.key") is False

    def test_exact_pattern(self, validator: SafePathValidator):
        """정확한 패턴 매칭"""
        assert validator._match_pattern(".env", ".env") is True
        assert validator._match_pattern(".env.local", ".env") is False

    def test_env_variants_pattern(self, validator: SafePathValidator):
        """환경 파일 변형 패턴"""
        assert validator._match_pattern(".env.local", ".env.*") is True
        assert validator._match_pattern(".env.production", ".env.*") is True


class TestSubpathCheck:
    """하위 경로 확인 테스트"""

    def test_is_subpath_true(self):
        """하위 경로인 경우"""
        parent = Path("/home/user/project")
        child = Path("/home/user/project/src/main.py")

        assert SafePathValidator._is_subpath(child, parent) is True

    def test_is_subpath_false(self):
        """하위 경로가 아닌 경우"""
        parent = Path("/home/user/project")
        other = Path("/home/user/other/file.py")

        assert SafePathValidator._is_subpath(other, parent) is False

    def test_is_subpath_same_path(self):
        """동일 경로"""
        path = Path("/home/user/project")

        # 동일 경로는 하위 경로가 아님 (relative_to는 빈 경로 반환)
        # 하지만 우리 로직에서는 같은 경로도 허용함
        # validate에서 path == allowed_resolved로 처리됨
        assert SafePathValidator._is_subpath(path, path) is True
