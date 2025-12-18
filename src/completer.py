"""슬래시 명령어 자동완성 관련 모듈"""

from typing import Iterable

from prompt_toolkit.completion import Completer, Completion


class SlashCompleter(Completer):
    """슬래시 명령어 자동완성

    - '/' 로 시작하는 입력만 자동완성 대상
    - COMMANDS 리스트를 받아서 사용 (느슨한 결합)
    """

    def __init__(self, commands: list[tuple[str, str]]):
        """
        :param commands: (명령어, 설명) 튜플 리스트
        """
        self.commands = commands

    def get_completions(self, document, complete_event) -> Iterable[Completion]:
        text = document.text_before_cursor

        # '/'로 시작할 때만 자동완성
        if not text.startswith("/"):
            return

        # '/' 이후 입력된 텍스트
        cmd_text = text[1:].lower()

        for cmd, desc in self.commands:
            if cmd.startswith(cmd_text):
                yield Completion(
                    cmd,
                    start_position=-len(cmd_text),
                    display=f"/{cmd}",
                    display_meta=desc,
                )
