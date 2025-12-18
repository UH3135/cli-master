# CLI Master

## 아키텍처 규칙

### main.py
- **조립(Composition) 전용**: main.py는 모듈을 조립하고 실행하는 역할만 수행
- 비즈니스 로직 작성 금지
- 새로운 기능은 반드시 src/ 하위 모듈에 구현

### 프로젝트 구조
```
main.py          # 진입점 (조립만)
src/
  commands.py    # 명령어 처리
  history.py     # 히스토리 관리
  models.py      # 데이터 모델
  completer.py   # 자동완성
  storage/       # 저장소 구현
```

## 코딩 컨벤션
- 주석은 한국어로 작성
- 로그 포맷팅은 `%s` 사용 (f-string 금지)
- 패키지 관리는 uv 사용
