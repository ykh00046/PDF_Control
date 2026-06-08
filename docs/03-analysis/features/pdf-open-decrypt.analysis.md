# PDF Open-with-Password + Remove Protection — Gap Analysis

> **Status**: ✅ Approved
> **PDCA**: pdf-open-decrypt
> **Match Rate**: 100% · **Tests**: 208 passed (+13)

## 1. 설계 대비 구현 매트릭스

| 설계 항목 | 구현 | 위치 | 상태 |
|---|---|---|---|
| `EncryptedPDFError`/`PasswordRequired`/`IncorrectPassword` | ✅ | `app/encryption.py` | ✅ |
| `open_document(path, password)` 인증 + 예외 | ✅ | `app/pdf_engine.py` | ✅ |
| `save_document_copy(password=)` 소스 복호화 | ✅ | `app/pdf_engine.py` | ✅ |
| `render_page_preview(password=)` | ✅ | `app/pdf_engine.py` | ✅ |
| 세션 `_password`/`is_encrypted` + 저장 재계산 | ✅ | `app/document_session.py` | ✅ |
| 프리뷰 워커 암호 전달 | ✅ | `viewer.py` payload + `render_worker.py` | ✅ |
| `controller.load_document(password)` + 예외 전파 | ✅ | `app/controller.py` | ✅ |
| `controller.is_current_encrypted()` | ✅ | `app/controller.py` | ✅ |
| 열기 프롬프트 루프(open + drop 공용) | ✅ | `handlers/file_handlers.py` | ✅ |
| `save_file_decrypted` + `_commit_save(decrypt=)` | ✅ | `handlers/file_handlers.py` | ✅ |
| File 메뉴 "보호 해제" 액션(Ctrl+Alt+D) | ✅ | `app/ui_menu.py` | ✅ |
| i18n 6키 en/ko | ✅ | `i18n/en.json`, `ko.json` | ✅ |
| 테스트 계획 10항목 | ✅ 13함수 | `tests/test_open_decrypt.py` | ✅ |

**매치율: 13/13 = 100%** → Iterate 불필요(≥90%).

## 2. 검증 결과

- 전체 스위트: **208 passed** (기존 195 + 신규 13, 회귀 0).
- mypy strict 게이트: **통과** (`app.encryption` 신규 예외 포함 0 errors).
- i18n parity: en/ko 키 세트 동기(파서티 테스트 그린).
- 하위 호환: 평문 PDF 열기/저장 경로 불변, 신규 파라미터 전부 keyword-optional.

## 3. 발견/처리한 이슈

- **소스 재오픈 깨짐 위험**: 저장·프리뷰가 소스를 파일 경로로 재오픈 → 암호화 파일이면
  인증 누락으로 깨짐. 세션 `_password` 단일 소유 + 전 경로 스레딩으로 해결.
- **저장 후 재바인드 인증**: 기존 수동 `authenticate(unlock_password())`를
  `open_document(out, new_password)`로 통합 → 암호화/복호화/평문 3경우 일관 처리.
- **레이어 보존**: 컨트롤러는 Qt 비의존 유지 — 예외만 전파, 프롬프트는 UI가 담당.

## 4. 알려진 한계 (문서화됨)

- 빈 사용자암호 + 소유자암호만 있는(프롬프트 없이 열리는) 파일은 `is_encrypted=False`로
  잡혀 "보호 해제" 액션이 비활성처럼 동작. 드문 케이스, 차기 후보.
- 프리뷰 워커 job JSON에 평문 암호가 일시 기록(임시 디렉터리, 렌더 직후 삭제). Starter
  데스크톱 범위에서 수용한 트레이드오프.
