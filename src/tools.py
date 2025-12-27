"""커스텀 도구 정의"""

import re
import os
import glob as glob_module

from langchain_core.tools import tool, BaseTool


@tool
def cat(file_path: str) -> str:
    """파일 내용을 읽습니다.

    Args:
        file_path: 읽을 파일 경로

    Returns:
        파일 내용 또는 오류 메시지
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content
    except FileNotFoundError:
        return f"오류: '{file_path}' 파일을 찾을 수 없습니다"
    except PermissionError:
        return f"오류: '{file_path}' 파일에 대한 읽기 권한이 없습니다"
    except Exception as e:
        return f"파일 읽기 오류: {e}"


@tool
def tree(path: str = ".", max_depth: int = 3) -> str:
    """디렉토리 구조를 트리 형태로 표시합니다.

    Args:
        path: 시작 디렉토리 경로 (기본: 현재 디렉토리)
        max_depth: 최대 깊이 (기본: 3)

    Returns:
        디렉토리 트리 구조
    """
    def build_tree(dir_path: str, prefix: str = "", depth: int = 0) -> list:
        if depth >= max_depth:
            return []

        lines = []
        try:
            entries = sorted(os.listdir(dir_path))
        except PermissionError:
            return [f"{prefix}[권한 없음]"]

        # 숨김 파일/디렉토리 및 일반적인 제외 항목 필터링
        exclude = {'.git', '__pycache__', 'node_modules', '.venv', 'venv'}
        entries = [e for e in entries if e not in exclude and not e.startswith('.')]

        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            connector = "└── " if is_last else "├── "
            entry_path = os.path.join(dir_path, entry)

            if os.path.isdir(entry_path):
                lines.append(f"{prefix}{connector}{entry}/")
                extension = "    " if is_last else "│   "
                lines.extend(build_tree(entry_path, prefix + extension, depth + 1))
            else:
                lines.append(f"{prefix}{connector}{entry}")

        return lines

    if not os.path.exists(path):
        return f"오류: '{path}' 경로를 찾을 수 없습니다"

    if not os.path.isdir(path):
        return f"오류: '{path}'는 디렉토리가 아닙니다"

    result = [f"{path}/"]
    result.extend(build_tree(path))
    return "\n".join(result)


@tool
def grep(pattern: str, path: str = ".", file_pattern: str = "*") -> str:
    """파일에서 텍스트 패턴을 검색합니다.

    Args:
        pattern: 검색할 텍스트 또는 정규식 패턴
        path: 검색할 디렉토리 (기본: 현재 디렉토리)
        file_pattern: 파일 패턴 (기본: 모든 파일)

    Returns:
        검색 결과 (파일 경로와 줄 번호 포함)
    """
    results = []
    pattern_re = re.compile(pattern)

    search_pattern = os.path.join(path, "**", file_pattern)
    for file_path in glob_module.glob(search_pattern, recursive=True):
        if os.path.isfile(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        if pattern_re.search(line):
                            results.append(
                                f"{file_path}:{line_num}: {line.strip()}"
                            )
            except (OSError, UnicodeDecodeError):
                pass

    if not results:
        return f"'{pattern}' 패턴과 일치하는 결과를 찾지 못했습니다"

    return "\n".join(results[:50])  # 최대 50개 결과


def get_tools() -> list[BaseTool]:
    """모듈 내 모든 도구 자동 수집"""
    return [obj for obj in globals().values() if isinstance(obj, BaseTool)]
