# R4 Bugfix - Design

> **Summary**: 검증된 버그 3건(B1 mypy.ini 인코딩 / B2 from_dict wrap 누락 / B3 비밀번호 평문 디스크)의 구체 수정 설계
>
> **Author**: Claude (bkit)
> **Created**: 2026-06-10
> **Status**: ✅ Completed (2026-06-10, 매치율 100%)
> **Plan**: [r4-bugfix.plan.md](../../01-plan/features/r4-bugfix.plan.md)

---

## 1. B1 — mypy.ini ASCII 정리

### 원인 메커니즘

mypy `config_parser._parse_individual_file`은 ini 파일을 **인코딩 미지정 텍스트 모드**로 열어 로케일 기본값(한국어 Windows = cp949)으로 읽는다. `mypy.ini:19`의 `—`(U+2014, UTF-8 `E2 80 94`)에서 `UnicodeDecodeError` → mypy 자체가 기동 실패 → `test_mypy.py` 2개 실패.

### 수정

```diff
-# Backward-compat shim — re-export only. Strict is enforced on the real
+# Backward-compat shim -- re-export only. Strict is enforced on the real
```

파일 머리에 재발 방지 주석 추가(ASCII로):

```ini
# NOTE: keep this file ASCII-only. mypy reads it with the locale default
# encoding (cp949 on Korean Windows), so any non-ASCII byte breaks mypy.
```

### 검증

- `[System.IO.File]::ReadAllBytes`로 비ASCII 0개 확인.
- `test_mypy.py` 2개 통과.

---

## 2. B2 — `Operation.from_dict` wrap 복원

### 수정 (`app/operations/base.py` RedactReplace 분기)

```python
return RedactReplace(
    page_index, rects, data["new_text"],
    data.get("fontname", "helv"), data.get("fontsize", 0),
    data.get("align", 0), data.get("fontfile", None),
    tuple(color) if color else None,
    data.get("font_flags", 0),
    wrap=data.get("wrap", None),   # ← 추가. 키 부재(구버전 데이터) = None = 전역 따름
)
```

`RedactReplace.__init__`의 `wrap` 키워드는 이미 존재(`redact.py:32`) — 시그니처 변경 없음.

### 재발 방지 테스트 — 신규 `tests/test_op_serialization.py`

op 4종 × round-trip 동등성:

```
test_operation_from_dict_round_trip
  - RedactDelete(page, rects)
  - RedactReplace(..., wrap=True), (..., wrap=False), (..., wrap=None)  ← 핵심
  - CropMargins(page, top/bottom/left/right)
  - RemoveSectionAsImage(page, remove_rect, dpi, format)
  검증: op.to_dict() == Operation.from_dict(op.to_dict()).to_dict()
```

`to_dict` 사전 비교 방식이라 필드 추가 시 자동으로 그물에 걸린다(향후 동일 유형 회귀 차단).

---

## 3. B3 — 비밀번호 stdin 전달 + 캡슐화

### 데이터 흐름 (변경 후)

```
viewer._start_render_process
  payload = {..., "password_stdin": true}     # 비번 문자열은 파일에 안 씀
  job.json 기록 (평문 비번 없음)
  Popen(..., stdin=PIPE)
  process.stdin.write(password + "\n"); process.stdin.close()
        │
        ▼
main.py --render-worker job.json
  run_render_job(job_path)
    job["password_stdin"] == True
      → password = sys.stdin.readline().rstrip("\n") or None
    render_page_preview(..., password=password)   # 기존 시그니처 그대로
```

### 변경 상세

**`app/document_session.py`** — 읽기 접근자 신설(기존 `_password` 소유권 불변):

```python
def render_password(self) -> "Optional[str]":
    """Password for re-opening the encrypted source (render worker 등).

    평문 반환이므로 디스크에 기록하지 말 것. 비암호화 문서는 None.
    """
    return self._password if self.is_encrypted else None
```

**`app/viewer.py` `_start_render_process`**:

1. `payload["password"]` 제거. `password = self.session.render_password()` 후
   `password is not None`이면 `payload["password_stdin"] = True`만 기록.
2. `subprocess.Popen(..., stdin=subprocess.PIPE if password is not None else subprocess.DEVNULL)`.
   `encoding="utf-8"` + `errors="replace"`(워커 stderr가 로케일 인코딩일 수 있어 하드페일 방지).
3. spawn 성공 직후:
   ```python
   if password is not None and process.stdin is not None:
       try:
           process.stdin.write(password + "\n")
       finally:
           process.stdin.close()
   ```
   - `BrokenPipeError`/`OSError`는 무시하지 않고 기존 `_on_render_error` 경로로 — 워커가 즉사한 경우 response 폴링이 에러를 회수하므로 write 실패는 `except OSError: pass`로 흡수해도 안전(워커 쪽 실패가 곧 표면화됨). **채택: 흡수 + debug 로그**.
4. `session._password` 직접 참조 제거(이 한 곳뿐임을 grep으로 확인).

**`app/render_worker.py` `run_render_job`**:

```python
password = None
if job.get("password_stdin"):
    # One-line protocol: viewer writes the password followed by "\n" and
    # closes the pipe. Passwords containing "\n" are not supported.
    password = sys.stdin.readline().rstrip("\n") or None
...
render_page_preview(..., password=password)
```

- 플래그 없으면 stdin을 건드리지 않음 → 기존 비암호화 경로 100% 불변.
- `text=True` Popen이므로 워커 쪽 `sys.stdin`도 텍스트 모드 — 인코딩은 둘 다 로케일 기본이라 일치. 단 비ASCII 비번의 인코딩 불일치 위험을 없애기 위해 **Popen에 `encoding="utf-8"` 명시 + 워커에서 `sys.stdin.reconfigure(encoding="utf-8")`** (worker 진입 시 1회).

### 테스트 — 신규 `tests/test_render_password_channel.py`

| 테스트 | 검증 |
|---|---|
| `test_viewer_job_file_has_no_password` | 암호화 세션으로 `_start_render_process` 호출(Popen 모킹) 후 job 파일 JSON에 `"password"` 키 부재, `"password_stdin"` == True, stdin 파이프로 비번 전송+close |
| `test_viewer_plain_document_uses_no_stdin_pipe` | 평문 세션 → 플래그·비번 모두 없음, `stdin=DEVNULL` |
| `test_worker_reads_password_from_stdin` | `run_render_job`을 stdin monkeypatch(`io.StringIO("pw\n")`)로 호출 → 암호화 PDF 렌더 성공(출력 PNG 생성) |
| `test_worker_without_flag_never_touches_stdin` | 플래그 없는 job → stdin 안 읽음(읽으면 예외 나는 stdin 주입) + 평문 PDF 렌더 성공 |
| `test_render_password_*` (accessor 2종) | 암호화 세션 → 비번 반환 / 평문 세션 → None |

---

## 4. 구현 순서

1. B1 (`mypy.ini`) → `test_mypy.py` 단독 실행으로 즉시 확인
2. B2 (`base.py` 1줄 + round-trip 테스트)
3. B3 (session 접근자 → render_worker stdin → viewer 발신부 → 테스트 4종)
4. 전체 스위트 (Python 3.13 절대경로)

## 5. 하위 호환 매트릭스

| 시나리오 | 변경 전 | 변경 후 |
|---|---|---|
| 비암호화 PDF 렌더 | password 키 없음 | 동일 (플래그도 없음, stdin 미사용) |
| 암호화 PDF 렌더 | 평문 비번 job 파일 | 플래그 + stdin (기능 동일, 디스크 노출 제거) |
| 구버전 직렬 op(wrap 키 없음) | wrap=None 복원(우연히 정상) | wrap=None 복원(명시적) |
| wrap 지정 op 미리보기 | **무시됨(버그)** | 반영 |
