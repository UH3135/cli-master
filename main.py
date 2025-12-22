"""CLI Master - 대화 세션을 저장하는 CLI 도구"""

import logging

from rich.console import Console
from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style
from prompt_toolkit.key_binding import KeyBindings

from src.config import config
from src.history import SqlHistory
from src.commands import CommandHandler
from src.completer import SlashCompleter
from src import agent

logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# prompt_toolkit 스타일 정의
prompt_style = Style.from_dict(
    {
        "prompt": "bold green",
        "completion-menu.completion": "bg:#333333 #ffffff",
        "completion-menu.completion.current": "bg:#00aa00 #000000",
        "completion-menu.meta.completion": "bg:#333333 #888888",
        "completion-menu.meta.completion.current": "bg:#00aa00 #000000",
    }
)


def main():
    console = Console()

    console.print("[bold cyan]CLI Master[/bold cyan]")

    # 히스토리 및 자동완성 초기화
    history = SqlHistory(config.DATABASE_URL)
    handler = CommandHandler(console, history)
    completer = SlashCompleter()

    console.print("[dim]Ctrl+C: 현재 입력 취소 | Shift+Enter: 줄바꿈 | /: 명령어 보기[/dim]\n")

    # 키 바인딩 설정: Enter=제출, Shift+Enter=줄바꿈
    bindings = KeyBindings()

    @bindings.add("s-enter")
    def _(event):
        """Shift+Enter: 줄바꿈 삽입"""
        event.current_buffer.insert_text("\n")

    session = PromptSession(
        "> ",
        style=prompt_style,
        completer=completer,
        complete_while_typing=True,
        history=history,
        multiline=True,
        key_bindings=bindings,
    )

    while handler.running:
        try:
            # 방향키 ↑/↓로 이전·다음 입력 탐색 가능
            user_input = session.prompt()

            if user_input.startswith("/"):
                handler.handle(user_input)
            elif user_input.strip():
                console.print("[bold cyan]AI:[/bold cyan] ", end="")
                for chunk in agent.stream(user_input):
                    console.print(chunk, end="")
                console.print()

        except KeyboardInterrupt:
            # Ctrl+C: 현재 입력 무시하고 계속
            console.print("\n[yellow]입력이 취소되었습니다[/yellow]")
            continue
        except EOFError:
            # Ctrl+D: 종료
            console.print("\n[blue]프로그램을 종료합니다[/blue]")
            break


if __name__ == "__main__":
    main()
