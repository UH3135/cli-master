"""CLI Master - 대화 세션을 저장하는 CLI 도구"""

from rich.console import Console
from rich.live import Live
from rich.text import Text
from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style
from prompt_toolkit.key_binding import KeyBindings

from .config import config
from .history import SqlHistory
from .commands import CommandHandler
from .completer import SlashCompleter
from .log import setup_logging
from . import agent

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
    setup_logging()
    console = Console()

    console.print("[bold cyan]CLI Master[/bold cyan]")

    # 히스토리 및 자동완성 초기화
    history = SqlHistory(config.DATABASE_URL)
    handler = CommandHandler(console, history)
    completer = SlashCompleter()

    console.print("[dim]Ctrl+C: 현재 입력 취소 | Enter: 제출 | Alt+Enter: 줄바꿈 | /: 명령어 보기[/dim]\n")

    # 키 바인딩 설정: Enter=제출, Alt+Enter=줄바꿈
    bindings = KeyBindings()

    @bindings.add("escape", "enter")
    def _(event):
        """Alt+Enter: 줄바꿈 삽입"""
        event.current_buffer.insert_text("\n")

    session = PromptSession(
        "> ",
        style=prompt_style,
        completer=completer,
        complete_while_typing=True,
        history=history,
        multiline=False,
        key_bindings=bindings,
    )

    while handler.running:
        try:
            # 방향키 ↑/↓로 이전·다음 입력 탐색 가능
            user_input = session.prompt()

            if user_input.startswith("/"):
                handler.handle(user_input)
            elif user_input.strip():
                logs = []
                final_response = None

                def truncate(s: str, max_len: int = 60) -> str:
                    """긴 문자열 축약"""
                    return s[:max_len] + "..." if len(s) > max_len else s

                with Live(Text("답변 생성 중...", style="dim"), transient=True) as live:
                    for event_type, data in agent.stream(user_input):
                        if event_type == "tool_start":
                            args_str = truncate(data["args"])
                            logs.append(f"⚙ {data['name']} 실행 중...\n  → {args_str}")
                            live.update(Text("\n".join(logs), style="dim"))
                        elif event_type == "tool_end":
                            result_str = truncate(data["result"])
                            logs.append(f"  ✓ 완료: {result_str}")
                            live.update(Text("\n".join(logs), style="dim"))
                        elif event_type == "response":
                            final_response = data

                if final_response:
                    console.print(f"[bold cyan]AI:[/bold cyan] {final_response}")
                    history.store_ai_response(final_response)

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
