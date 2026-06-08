# PDF Open-with-Password + Remove Protection — Design

> **Status**: ✅ Approved (as-built v1.0)
> **PDCA**: pdf-open-decrypt
> **Plan**: [../../01-plan/features/pdf-open-decrypt.plan.md](../../01-plan/features/pdf-open-decrypt.plan.md)

---

## 1. 아키텍처 개요

암호는 **세 가지 흐름**에서 필요하다. 핵심 원칙: 세션이 `_password`를 단일 소유하고,
*소스를 재오픈하는 모든 경로*에 전달한다.

```
열기:   open_file ──prompt loop──▶ controller.load_document(path, pw)
              │  PasswordRequired / IncorrectPassword (전파)
              ▼
        DocumentSession(path, pw) ── open_document(path, pw) ──▶ fitz.open + authenticate
              └ self._password = pw ; self.is_encrypted = pw is not None

프리뷰:  viewer._start_render_process ─ job["password"]=session._password ─▶ render_worker
              └▶ render_page_preview(path, ..., password) ── open_document(path, pw)

저장:   save_document(out, encryption) ── save_document_copy(src, out, ..., password=self._password, encryption)
              │  (src 재오픈에 password / out 쓰기에 encryption — 독립)
              └▶ reload: open_document(out, new_password)  where new_password = enc.unlock() or None
                 self._password = new_password ; self.is_encrypted = bool(new_password)

해제:   save_file_decrypted ── 가드(is_encrypted) ─▶ _commit_save(encryption=None, decrypt=True)
              └ encryption=None → save_kwargs 비어있음 → 평문 저장(자연 복호화)
```

## 2. 예외 (app/encryption.py — strict, 순수)

```python
class EncryptedPDFError(Exception): ...           # 공통 베이스
class PasswordRequired(EncryptedPDFError): ...    # 암호 필요, 미입력
class IncorrectPassword(EncryptedPDFError): ...   # 암호 오답
```

저장-정책 모듈(`encryption.py`)에 두는 이유: "암호화" 도메인의 일부이고, 예외는 의존성 없는
순수 클래스라 strict 게이트와 충돌하지 않음.

## 3. 엔진 경계 (app/pdf_engine.py)

```python
def open_document(file_path: str, password: str | None = None) -> fitz.Document:
    doc = fitz.open(file_path)
    if doc.needs_pass:
        if password is None:
            doc.close(); raise PasswordRequired(file_path)
        if not doc.authenticate(password):   # 0 == 실패
            doc.close(); raise IncorrectPassword(file_path)
    return doc
```

- `save_document_copy(..., password=None)`: `document = open_document(source_path, password)`.
  `encryption`(출력 암호화)과 `password`(소스 복호화)는 **독립 파라미터**.
- `render_page_preview(..., password=None)`: `source_doc = open_document(file_path, password)`.

## 4. 세션 (app/document_session.py)

- `__init__(file_path, password=None)`: `open_document(file_path, password)` 호출,
  `self._password = password`, `self.is_encrypted = password is not None` 저장.
- `save_document(output_path, encryption=None)`:
  - `save_document_copy(self.file_path, output_path, self.history, password=self._password, encryption=encryption)`
  - `new_password = encryption.unlock_password() if encryption and encryption.is_active() else None`
  - `reloaded = open_document(output_path, password=new_password)` (기존 수동 authenticate 대체)
  - `self._password = new_password`, `self.is_encrypted = bool(new_password)`

## 5. 컨트롤러 (app/controller.py)

```python
def load_document(self, file_path, password=None) -> bool:
    try:
        new_session = DocumentSession(file_path, password=password)
    except EncryptedPDFError:
        raise                       # UI가 프롬프트 처리 (error_occurred emit 안 함)
    except Exception as e:
        self.error_occurred.emit(...); return False
    ... 세션 스왑 ...
```

`is_current_encrypted()` 헬퍼: `bool(session and session.is_encrypted)` — 메뉴 가드용.

## 6. UI (app/handlers/file_handlers.py)

- `_load_with_password_prompt(file_path) -> bool`: open_file / dropEvent 공용.
  ```
  password = None
  while True:
      try: return controller.load_document(file_path, password)
      except PasswordRequired:  title=prompt
      except IncorrectPassword: title=retry
      pw, ok = QInputDialog.getText(..., echo=Password)
      if not ok: status(cancelled); return False
      password = pw
  ```
- `save_file_decrypted()`: `session` 없음/비암호화 시 상태바 안내 후 종료, 아니면
  `_commit_save(encryption=None, decrypt=True)`.
- `_commit_save(encryption=None, decrypt=False)`: 제안 파일명 접미사(`_decrypted.pdf` vs
  `_edited.pdf`)와 성공 메시지(`status.decrypted` / `saved_encrypted` / `saved`) 분기.

## 7. 메뉴 (app/ui_menu.py)

File 메뉴에 "암호화하여 저장" 다음, 구분선 위에 **"보호 해제(복호화)..."** 추가
(`win.save_file_decrypted`). 단축키 `Ctrl+Alt+D`. 런타임 가드(항상 표시, 비암호화 시 안내).

## 8. 프리뷰 워커 (app/render_worker.py, app/viewer.py)

- viewer payload에 `"password": self.session._password`(암호화 세션일 때만; 평문은 키 생략/None).
- render_worker: `render_page_preview(..., password=job.get("password"))`.
- **보안 트레이드오프**: 평문 암호가 임시 job JSON에 잠깐 기록됨. 임시 디렉터리에 쓰고
  렌더 직후 `_cleanup_render_files`로 삭제. Starter 데스크톱 앱 범위에서 수용, 문서화.

## 9. i18n 키 (en/ko)

| 키 | 용도 |
|---|---|
| `dialog.password.title` | 비밀번호 프롬프트 제목 |
| `dialog.password.prompt` | "이 PDF는 암호로 보호되어 있습니다. 비밀번호:" |
| `dialog.password.retry` | "비밀번호가 올바르지 않습니다. 다시 입력하세요:" |
| `menu.file.remove_protection` | "보호 해제(복호화)..." |
| `status.decrypted` | "보호 해제됨 — 저장: {0}" |
| `status.not_encrypted` | "현재 문서는 암호로 보호되어 있지 않습니다" |
| `status.cancelled_open` | (기존 재사용) |

## 10. 테스트 계획

순수/엔진 레벨(Qt 비의존)에 집중:

1. `open_document(encrypted)` → `PasswordRequired`
2. `open_document(encrypted, "wrong")` → `IncorrectPassword`
3. `open_document(encrypted, ok)` → 페이지 접근 가능
4. `open_document(plain, "any")` → 정상(평문은 암호 무시)
5. `DocumentSession(encrypted, pw)` → `is_encrypted` True, `doc[0].get_text()` 정상
6. `DocumentSession(encrypted)` (무암호) → `PasswordRequired`
7. 라운드트립: 암호화 저장 → 세션 재오픈 → 일반 저장(복호화) → `needs_pass False` + 내용 보존
8. `save_document_copy(password=...)` 가 암호화 소스를 읽어 ops 적용
9. 복호화 저장 후 `session.is_encrypted` False
10. 하위 호환: 기존 191 테스트 그린 유지

신규 픽스처 `encrypted_pdf`(conftest): user_password="open123"로 보호된 1페이지 PDF.

## 11. 결정 로그

| 질문 | 결정 |
|---|---|
| 암호를 어디서 보관? | 세션 `_password` 단일 소유, 모든 재오픈에 스레딩 |
| 프롬프트 위치? | UI(file_handlers) 루프, 컨트롤러는 예외만 전파(레이어 보존) |
| 복호화는 신규 저장 경로? | 아니오 — 기존 `_commit_save(encryption=None)` 재사용(평문 저장=자연 복호화) |
| 프리뷰 암호 전달? | job JSON에 포함(임시·즉시 삭제). 대안(세션 전체 평문 temp 사본)은 노출 범위가 더 커서 기각 |
| 예외 위치? | `encryption.py`(도메인 일치 + 순수 클래스, strict 무해) |
