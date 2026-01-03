"""Short Term 저장소: 프롬프트 입력 히스토리 관리"""

from prompt_toolkit.history import InMemoryHistory, History


class PromptHistoryRepository:
    """InMemoryHistory 래핑 - 확장 가능한 구조

    prompt_toolkit의 InMemoryHistory를 래핑하여
    내부 구현(_storage) 노출 없이 관리
    """

    def __init__(self) -> None:
        self._history = InMemoryHistory()

    def get_history(self) -> History:
        """prompt_toolkit History 객체 반환 (PromptSession용)"""
        return self._history

    def add_entry(self, text: str) -> None:
        """히스토리 항목 추가"""
        self._history.store_string(text)

    def clear(self) -> None:
        """히스토리 초기화"""
        if hasattr(self._history, "_storage"):
            self._history._storage.clear()

    def load_from_messages(self, messages: list[str]) -> None:
        """메시지 목록으로 히스토리 갱신 (기존 내용 대체)"""
        self.clear()
        for msg in messages:
            self.add_entry(msg)

    def get_entries(self) -> list[str]:
        """모든 히스토리 항목 반환"""
        if hasattr(self._history, "_storage"):
            return list(self._history._storage)
        return []
