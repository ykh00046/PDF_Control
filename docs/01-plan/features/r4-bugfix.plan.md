# R4 Bugfix - Plan

> **Summary**: 2026-06-10 전체 검토에서 검증된 버그 3건 일괄 수정 — (B1) mypy.ini 인코딩으로 깨진 mypy 게이트 복구, (B2) `Operation.from_dict`의 `wrap` 누락으로 인한 preview≠save 회귀 수정, (B3) 렌더 워커 비밀번호 평문 디스크 기록 제거 + `_password` 캡슐화
>
> **Author**: Claude (bkit)
> **Created**: 2026-06-10
> **Status**: ✅ Completed (2026-06-10, 매치율 100%, 221 passed)
> **Cycle**: r4-bugfix

---

## 1. 배경 (Why)

2026-06-10 프로젝트 전체 검토(code-analyzer + 직접 검증)에서 다음 3건이 **실코드/실행으로 확인**됐다. 현재 테스트 스위트가 206/208로 깨져 있는 상태(B1)라 후속 사이클 진행 전 선행 수정이 필수다.

### B1. mypy 게이트 테스트 2개 실패 (현재 깨짐)

`mypy.ini:19` 주석의 em-dash(`—`, U+2014, UTF-8 3바이트) 때문에 한국어 Windows(cp949 로케일)에서 mypy가 config 파싱 중 `UnicodeDecodeError`로 즉사한다. mypy의 `configparser` 읽기가 로케일 기본 인코딩을 쓰기 때문. `test_mypy.py` 2개 테스트 실패 → **206 passed, 2 failed**.

### B2. preview≠save 회귀 — `from_dict`가 `wrap` 복원 누락

`RedactReplace.to_dict()`는 `wrap`을 직렬화하지만(`app/operations/redact.py:61`) `Operation.from_dict`(`app/operations/base.py:53-59`)는 재구성 시 `wrap`을 전달하지 않는다. 렌더 워커는 항상 `from_dict`로 op를 복원하므로(`render_worker.py:23`) **미리보기는 replace-wrap-toggle에서 고른 줄바꿈/축소 선택을 무시**하고 전역 `TEXT_WRAP_ENABLED`로 렌더한다. 저장은 메모리상 op를 직접 적용하므로 wrap이 반영됨 → 프로젝트가 보증하는 **preview=save 등가성 위반**. op 직렬화 round-trip 테스트 부재가 미검출 원인.

### B3. 렌더 비밀번호 평문 디스크 기록 (보안)

`app/viewer.py:148-152` — 암호화 PDF 미리보기마다 비밀번호를 temp 디렉터리의 평문 job JSON에 기록한다. 정상 경로는 렌더 후 삭제하지만 **크래시·강제종료 시 잔존**하고, 공용 temp는 타 사용자가 읽을 수 있다. 또한 viewer가 `session._password` private 속성을 직접 접근한다(캡슐화 위반).

---

## 2. 목표 (What)

### 필수 (Must)

- **M1 (B1)**: `mypy.ini`를 ASCII-only로 정리(em-dash → `--`). `test_mypy.py` 2개 복구 → 208 passed.
- **M2 (B2)**: `Operation.from_dict`의 `RedactReplace` 분기에 `wrap=data.get("wrap", None)` 전달. 기존 직렬 데이터(wrap 키 없음)는 `None`(전역 따름)으로 복원 — 하위 호환.
- **M3 (B2 재발 방지)**: 4개 op 타입 전부에 대한 `to_dict → from_dict` round-trip 동등성 테스트 신설.
- **M4 (B3)**: 비밀번호를 job 파일에 쓰지 않는다. **stdin 채널**로 워커에 전달: viewer가 `Popen(stdin=PIPE)`로 띄우고 비밀번호 1줄 기록 후 close, job JSON에는 `"password_stdin": true` 플래그만. 워커는 플래그 감지 시 stdin에서 읽는다.
- **M5 (B3)**: `DocumentSession`에 읽기 접근자(`render_password()` 또는 property) 신설, viewer의 `session._password` 직접 접근 제거.

### 권장 (Should)

- **S1**: B3 가드 테스트 — 암호화 세션 렌더 시 job 파일 내용에 `password` 키가 없음을 검증.
- **S2**: `mypy.ini`에 "ASCII only — cp949 locale reads this file" 주석(ASCII로) 추가해 재발 방지.

### 범위 외 (Won't)

- 메모리 내 `_password` 평문 보관 자체의 해소(SecureString 등) — 데스크톱 앱 위협 모델에서 과설계, 보류.
- CI 도입·의존성 고정·pyproject 통합 — **R5 인프라 사이클**.
- controller 예외 가드 공통화, applicator 분해 — **R6 품질 사이클**.

---

## 3. 성공 기준 (Acceptance)

- [ ] 전체 테스트 **208개 이상 전부 통과** (Python 3.13, 신규 테스트 포함 시 그 이상).
- [ ] `mypy.ini` 비ASCII 바이트 0개.
- [ ] **신규 테스트**: op 4종 round-trip — `RedactReplace(wrap=True/False/None)` 포함 모든 필드 보존.
- [ ] **신규 테스트**: 렌더 job 파일에 평문 비밀번호 부재 + 워커가 stdin 비밀번호로 암호화 PDF 렌더 성공.
- [ ] viewer에 `session._password` 직접 참조 0건.
- [ ] Gap 분석 매치율 ≥ 90%.

---

## 4. 영향 범위 (Scope)

| 파일 | 변경 |
|---|---|
| `mypy.ini` | em-dash 1글자 → ASCII (B1) |
| `app/operations/base.py` | `from_dict`에 `wrap` 전달 (B2) |
| `app/viewer.py` | payload에서 password 제거, `password_stdin` 플래그 + `Popen(stdin=PIPE)` + 접근자 사용 (B3) |
| `app/render_worker.py` | `password_stdin` 플래그 시 stdin에서 비밀번호 읽기 (B3) |
| `app/document_session.py` | `render_password()` 읽기 접근자 추가 (B3) |
| `tests/test_open_decrypt.py` 또는 신규 | stdin 전달·job 파일 무비번 가드 테스트 |
| `tests/test_regressions.py` 또는 신규 | op round-trip 테스트 |

---

## 5. 리스크 & 완화

| 리스크 | 완화 |
|---|---|
| stdin 전달이 frozen(PyInstaller) 모드에서 다르게 동작 | 워커 진입점(`main.py --render-worker`)은 frozen/비frozen 동일 경로, stdin 의미 동일. `password_stdin` 미설정 시 기존 동작(비번 없음) 유지 |
| 비밀번호에 개행 포함 가능성 | PDF 표준상 비번은 Latin-1/UTF-8 문자열, 개행 포함 비현실적. `readline().rstrip("\n")`으로 1줄 프로토콜 고정, 한계는 docstring 명시 |
| `from_dict` 변경이 기존 직렬 데이터 깨뜨림 | `data.get("wrap", None)` — 키 부재 시 기존과 동일한 `None` |
| 워커가 stdin을 기다리며 행 | 플래그가 있을 때만 읽기. viewer는 spawn 직후 write+close 보장 (`finally`) |
