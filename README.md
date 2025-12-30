# CLI Master

AI 에이전트 기반 CLI 도구

## 설치

```bash
uv sync
```

## 환경 설정

`.env` 파일을 생성하고 다음 환경 변수를 설정합니다:

```bash
# Google AI API 키 (Gemini 2.5 Flash 사용)
GOOGLE_API_KEY=your_google_api_key_here

# 데이터베이스 연결 문자열 (선택, 기본값: sqlite:///db/history.db)
DATABASE_URL=sqlite:///db/history.db
```

### Google API 키 발급 방법

1. [Google AI Studio](https://aistudio.google.com/apikey)에 접속
2. Google 계정으로 로그인
3. "Create API Key" 클릭하여 API 키 생성
4. 생성된 키를 `.env` 파일의 `GOOGLE_API_KEY`에 설정

## 실행

```bash
uv run cli-master
```

## 프로젝트 구조

```
cli_master/
  main.py        # 진입점
  agent.py       # AI 에이전트 (LangGraph + Gemini)
  commands.py    # 명령어 처리
  config.py      # 환경 설정
  history.py     # 히스토리 관리
  models.py      # 데이터 모델
  completer.py   # 자동완성
  tools.py       # 커스텀 도구
```
