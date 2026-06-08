# PDF Open-with-Password + Remove Protection — Completion Report

> **Status**: ✅ Approved (Completed)
> **PDCA**: pdf-open-decrypt
> **Date**: 2026-06-08
> **Match Rate**: 100% · **Tests**: 208 passed (+13)

## Summary

선행 `pdf-encryption`이 만든 "쓰기 전용" 반쪽 상태를 닫았다. 이제 암호화 PDF를 **열 수
있고**(비밀번호 프롬프트 + 재시도), 보호된 문서의 **보호를 해제**(평문 사본 저장)할 수 있다.
편집·프리뷰·저장 전 경로가 암호화 소스에서도 동일하게 동작한다.

## What Shipped

| Layer | Change |
|-------|--------|
| Exceptions | `app/encryption.py` — `EncryptedPDFError`/`PasswordRequired`/`IncorrectPassword` (strict) |
| Engine | `open_document(path, password)` 인증+예외; `save_document_copy(password=)`, `render_page_preview(password=)` |
| Session | `DocumentSession(password=)` → `_password`/`is_encrypted`; save 시 재오픈 암호 재계산 |
| Preview | viewer payload `password`(암호화 세션 한정) → render_worker → engine |
| Controller | `load_document(password)` 예외 전파, `is_current_encrypted()` |
| UI | 열기/드롭 공용 프롬프트 루프(`_load_with_password_prompt`), `save_file_decrypted`, `_commit_save(decrypt=)` |
| Menu | File → "Remove Protection (Decrypt)…" (Ctrl+Alt+D) |
| i18n | `dialog.password.*`, `menu.file.remove_protection`, `status.decrypted`, `status.not_encrypted` (en/ko) |
| Tests | `tests/test_open_decrypt.py` (13) + `encrypted_pdf` 픽스처 |
| Docs | plan / design / analysis / report + CHANGELOG + CLAUDE.md |

## PDCA Cycle

- **Plan / Design**: 암호를 "소스를 재오픈하는 모든 경로"에 흐르는 세션 단일 소유 상태로 모델링.
- **Do**: 엔진 인증 경계 + 세션/컨트롤러/UI 스레딩 + 메뉴/i18n.
- **Check**: gap 100%; 소스 재오픈·재바인드 인증 두 함정을 식별·해결.
- **QA**: 208 ✅, mypy strict ✅, i18n parity ✅.
- **Act**: ≥90%이므로 반복 불필요.

## Design Decisions

- **세션이 암호 단일 소유**: 저장/프리뷰가 소스를 경로로 재오픈하는 기존 아키텍처와 일관.
  대안(열 때 평문 temp 사본 생성)은 세션 전체 평문 노출이라 노출 범위가 더 커서 기각.
- **복호화 = 평문 저장 재사용**: 별도 저장 경로를 만들지 않고 `_commit_save(encryption=None)`
  재사용. "보호 해제" 액션은 의도·접미사·메시지만 다른 얇은 변형.
- **레이어 보존**: 프롬프트 루프는 UI, 컨트롤러는 `EncryptedPDFError`만 전파.
- **하위 호환**: 신규 파라미터 전부 keyword-optional, 평문 경로 불변.

## Verification Notes

테스트 인터프리터는 Python 3.13(`...\Python313\python.exe`, pytest-qt + mypy 보유).
hermes venv에는 없으므로 UI/mypy 테스트는 3.13에서 실행. 전체 실행: **208 passed**.

## Follow-ups (future cycles)

- 빈 사용자암호 + 소유자암호만 있는 파일의 "암호화됨" 감지(현재 프롬프트 기준).
- 비밀번호 변경 전용 UX(현재는 "암호화하여 저장"으로 우회 가능).
- `typing-legacy-core`: `document_session`/`pdf_engine` strict 게이트 편입.
