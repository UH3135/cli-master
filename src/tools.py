"""커스텀 도구 정의"""

import re
import os
import glob as glob_module

from langchain_core.tools import tool, BaseTool


@tool
def edit_file(file_path: str, old_text: str, new_text: str) -> str:
    """파일의 일부를 수정합니다.

    Args:
        file_path: 파일 경로
        old_text: 찾을 텍스트
        new_text: 교체할 텍스트

    Returns:
        성공/실패 메시지
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if old_text not in content:
            return f"오류: '{old_text}'를 {file_path}에서 찾을 수 없습니다"

        new_content = content.replace(old_text, new_text)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        return f"{file_path} 파일이 성공적으로 수정되었습니다"
    except Exception as e:
        return f"파일 편집 오류: {str(e)}"


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
                            results.append(f"{file_path}:{line_num}: {line.strip()}")
            except:
                pass

    if not results:
        return f"'{pattern}' 패턴과 일치하는 결과를 찾지 못했습니다"

    return "\n".join(results[:50])  # 최대 50개 결과


def get_tools() -> list[BaseTool]:
    """모듈 내 모든 도구 자동 수집"""
    return [obj for obj in globals().values() if isinstance(obj, BaseTool)]
