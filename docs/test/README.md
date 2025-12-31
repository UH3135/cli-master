# 테스트 실행 방법

이 문서는 E2E 테스트를 실행하는 방법을 정리합니다.

## 사전 준비
- Python 3.12+
- 의존성 설치 (예: `uv sync` 또는 `pip install -e ".[dev]"`)

## E2E 테스트 실행
`pytest`로 E2E 테스트를 실행합니다.

```bash
pytest tests/test_e2e_cli.py
```

## 가짜 LLM 모드
E2E 테스트는 기본적으로 가짜 LLM 모드를 사용합니다.  
테스트 픽스처에서 `CLI_MASTER_FAKE_LLM=1`을 주입하므로 별도 설정이 필요 없습니다.

직접 실행할 때 가짜 LLM을 강제하려면 아래처럼 환경변수를 설정합니다.

```bash
CLI_MASTER_FAKE_LLM=1 python -m cli_master.main
```

## DB 격리
E2E 테스트는 `tmp_path` 기반으로 DB 경로를 주입합니다.
- `DATABASE_DIR`
- `DATABASE_URL`
- `CHECKPOINT_DB_PATH`

따라서 테스트끼리 데이터 충돌이 발생하지 않습니다.
