# Save Integrity - Gap Analysis

> **Summary**: 설계-구현 갭 분석 — 매치율 **100%**, 4개 회귀 리스크 전부 안전, Act 불필요
>
> **Analyzer**: bkit gap-detector
> **Date**: 2026-06-14
> **Design**: [save-integrity.design.md](../../02-design/features/save-integrity.design.md)

---

## 매치율: 100% (M1-M3 + S1 + Acceptance 1:1 반영)

| 항목 | 구현 증거 | 일치 |
|---|---|:--:|
| M1 `source_bytes` 파라미터 + source 분기 + encryption 독립 | `pdf_engine.py:93, 116-123` | ✅ |
| M2 `source_bytes=self.doc.tobytes()` 전달, rebind/clear/signals 불변 | `document_session.py:155, 161-173` | ✅ |
| M3-a~e 페이지 관리+저장 회귀 5종 | `test_page_management.py:420-495` (TestSaveIntegrity) | ✅ |
| M3 암호화 삭제+복호화 / 재암호화 | `test_open_decrypt.py:127-166` | ✅ |
| S1 docstring source 선택 의미 명시 | `pdf_engine.py:95-111` | ✅ |
| Acceptance 레거시 source_path 하위호환 | `test_save_copy_reads_encrypted_source` 불변 통과 | ✅ |

## 회귀 리스크 4종 점검 (전부 안전)

- **(a) 레거시 source_path 경로** — `source_bytes is None`이면 기존 코드와 바이트 동일. `source_bytes`를 넘기는 호출자는 `document_session.py` 하나뿐, 나머지(test_encryption/open_decrypt/regressions)는 전부 레거시 경로 불변.
- **(b) self.doc 비파괴** — `tobytes()`로 새 버퍼 → 엔진이 별개 Document를 열어 redaction 적용 → live `self.doc` 무손상. 저장 후 `_bind_document`로 출력 재바인드(기존 동작).
- **(c) 출력 암호화/복호화/재암호화** — `encryption` kwarg는 source 선택과 독립. 복호화·재암호화 라운드트립 테스트로 고정.
- **(d) password no-op** — source_bytes 경로는 password 미참조(평문 버퍼라 무의미), source_path 경로는 그대로 전달. 상호 간섭 0.

## 검증

- 전체 **268 passed** (261 + 신규 7), mypy strict(pdf_engine + document_session) 0 에러.
- probe: 인증된 암호화 doc의 `tobytes()`는 평문(needs_pass=0) + 페이지 변경 반영.

## 결론

매치율 100% ≥ 90%, 미승인 동작 변경 0 → Act 생략, Report 진행.
