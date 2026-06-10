# R4 Bugfix - Completion Report

> **Summary**: 2026-06-10 전체 검토에서 검증된 버그 3건 수정 완료 — mypy 게이트 복구(B1), preview≠save wrap 회귀 수정(B2), 렌더 비밀번호 평문 디스크 기록 제거(B3). 매치율 100%, **221 passed**(+13 신규)
>
> **Author**: Claude (bkit)
> **Completed**: 2026-06-10
> **Cycle**: r4-bugfix
> **Match Rate**: 100%

---

## 1. 무엇을 고쳤나

### B1. mypy 게이트 복구 (`mypy.ini`)

- **증상**: `test_mypy.py` 2개 실패 (206/208). 한국어 Windows(cp949)에서 mypy가 config 파싱 중 `UnicodeDecodeError`로 기동 실패.
- **원인**: `mypy.ini` 주석의 em-dash(U+2014) 1글자. mypy는 ini를 로케일 기본 인코딩으로 읽는다.
- **수정**: em-dash → `--`, 파일 머리에 ASCII-only 재발방지 주석.
- **교훈**: 도구 설정 파일은 ASCII-only가 안전. CI가 없어 커밋 후 로컬에서만 발견됨 → R5 CI 도입의 직접 근거.

### B2. preview≠save 회귀 (`app/operations/base.py`)

- **증상**: replace-wrap-toggle(2026-06-08)에서 추가한 교체별 줄바꿈/축소 선택이 **미리보기에서 무시**되고 전역 기본값으로 렌더됨. 저장은 정상 반영 → preview=save 등가성 위반.
- **원인**: `RedactReplace.to_dict()`는 `wrap`을 직렬화하지만 `Operation.from_dict`가 복원 시 누락. 렌더 워커는 항상 `from_dict` 경유.
- **수정**: `wrap=data.get("wrap", None)` 전달 (키 부재 = None = 전역 따름, 하위 호환).
- **재발 방지**: `tests/test_op_serialization.py` — op 4종 전체 `to_dict→from_dict` round-trip 동등성. 사전 전체 비교라 향후 필드 추가 누락도 자동 검출.

### B3. 렌더 비밀번호 평문 디스크 기록 제거 (보안)

- **증상**: 암호화 PDF 미리보기마다 비밀번호가 temp 디렉터리의 평문 job JSON에 기록. 크래시 시 잔존, 공용 temp에서 타 사용자 열람 가능.
- **수정**: 비밀번호를 **stdin 파이프**로 워커에 전달(1줄 프로토콜, UTF-8 양단 고정). job 파일에는 `password_stdin` 플래그만. `DocumentSession.render_password()` 접근자 신설로 `_password` 캡슐화(viewer의 private 직접 접근 제거).
- **하위 호환**: 비암호화 경로는 플래그 자체가 없어 바이트 단위 동일 동작. 플래그 없으면 워커는 stdin을 건드리지 않음(테스트로 보증).

## 2. 변경 파일

| 파일 | 변경 |
|---|---|
| `mypy.ini` | ASCII 정리 + 재발방지 주석 (B1) |
| `app/operations/base.py` | `from_dict` wrap 복원 (B2) |
| `app/document_session.py` | `render_password()` 접근자 (B3) |
| `app/render_worker.py` | `_read_password_from_stdin` + 플래그 처리 (B3) |
| `app/viewer.py` | 비번 디스크 기록 제거, stdin 파이프, utf-8/errors=replace (B3) |
| `tests/test_op_serialization.py` | 신규 — round-trip 7 테스트 (M3) |
| `tests/test_render_password_channel.py` | 신규 — 채널 보안 6 테스트 (M4/M5/S1) |

## 3. 검증 결과

- 전체 테스트: **221 passed, 0 failed** (Python 3.13) — 사이클 시작 시점 206 passed/2 failed에서 복구+확장
- mypy strict 게이트: 통과 (`app.operations` 포함 — base.py 수정분 strict 검증됨)
- Gap 분석: **매치율 100%** (M1-M5, S1-S2 전 항목) → Act 생략
- 알려진 한계: 개행 포함 비밀번호 미지원(1줄 프로토콜, PDF 비번 특성상 비현실적 — 워커 docstring 명시)

## 4. 다음 (로드맵)

- **R5 인프라**: CI(GitHub Actions: pytest+mypy, windows-latest) + requirements 버전 고정 + pyproject/ruff + 루트 정리(deprecated 문서·스크래치 스크립트·ui_handlers 셰임)
- **R6 품질**: controller 예외 가드 공통화, applicator 분해, pdf_engine→document_session strict 확장
- **R7 이후**: RemoveSection 비동기화, 히스토리 정책 통일, watermark, text-export-range
