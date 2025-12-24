"""도구 메타데이터 정의 - Vector 검색용"""

# 각 도구의 설명과 사용 예시
TOOL_METADATA = {
    "ls": {
        "name": "ls",
        "description": "디렉토리의 파일과 폴더 목록을 나열합니다.",
        "use_cases": [
            "폴더 안에 뭐가 있어?",
            "디렉토리 구조 보여줘",
            "파일 목록 확인",
            "현재 위치의 파일들",
        ],
        "keywords": ["목록", "리스트", "파일", "폴더", "디렉토리", "구조"],
    },
    "read_file": {
        "name": "read_file",
        "description": "파일의 내용을 읽어옵니다.",
        "use_cases": [
            "파일 내용 보여줘",
            "config.py 읽어줘",
            "코드 확인",
            "파일 열어서 보여줘",
        ],
        "keywords": ["읽기", "내용", "확인", "보기", "열기", "코드"],
    },
    "write_file": {
        "name": "write_file",
        "description": "새 파일을 생성하거나 기존 파일을 덮어씁니다.",
        "use_cases": [
            "파일 만들어줘",
            "새 파일 작성",
            "코드 저장",
            "파일에 쓰기",
        ],
        "keywords": ["생성", "작성", "만들기", "저장", "새로"],
    },
    "edit_file": {
        "name": "edit_file",
        "description": "기존 파일의 일부를 수정합니다.",
        "use_cases": [
            "파일 수정해줘",
            "코드 바꿔줘",
            "함수 고쳐줘",
            "일부 변경",
        ],
        "keywords": ["수정", "편집", "변경", "고치기", "바꾸기"],
    },
    "glob": {
        "name": "glob",
        "description": "파일 이름 패턴으로 파일을 검색합니다.",
        "use_cases": [
            "*.py 파일 찾아줘",
            "test로 시작하는 파일",
            "확장자가 .json인 파일들",
            "패턴으로 파일 검색",
        ],
        "keywords": ["패턴", "검색", "찾기", "확장자", "와일드카드", "*"],
    },
    "grep": {
        "name": "grep",
        "description": "파일 내용에서 특정 텍스트나 패턴을 검색합니다.",
        "use_cases": [
            "함수 정의 찾아줘",
            "TODO 주석 검색",
            "import 문 찾기",
            "코드에서 특정 문자열 검색",
        ],
        "keywords": ["검색", "찾기", "grep", "패턴", "텍스트", "문자열"],
    },
    "execute": {
        "name": "execute",
        "description": "셸 명령어를 실행합니다.",
        "use_cases": [
            "명령어 실행해줘",
            "git status 확인",
            "pytest 돌려줘",
            "스크립트 실행",
        ],
        "keywords": ["실행", "명령어", "shell", "터미널", "run", "git", "pytest"],
    },
}


def get_tool_embedding_text(tool_name: str) -> str:
    """도구를 임베딩하기 위한 텍스트 생성"""
    meta = TOOL_METADATA.get(tool_name)
    if not meta:
        return tool_name

    # 설명 + 사용 사례 + 키워드를 결합
    text_parts = [
        meta["description"],
        " ".join(meta["use_cases"]),
        " ".join(meta["keywords"]),
    ]
    return " ".join(text_parts)
