# Save Integrity - Design

> **Summary**: 저장 source를 현재 doc 복사본(`tobytes()`)으로 전환하는 구체 설계
>
> **Author**: Claude (bkit)
> **Created**: 2026-06-14
> **Status**: ✅ Completed (2026-06-14, 매치율 100%)
> **Plan**: [save-integrity.plan.md](../../01-plan/features/save-integrity.plan.md)

---

## 1. M1 — `pdf_engine.save_document_copy`

```python
def save_document_copy(
    source_path: str,
    output_path: str,
    operations: Sequence[Operation],
    logger: logging.Logger | None = None,
    encryption: EncryptionSettings | None = None,
    password: str | None = None,
    source_bytes: bytes | None = None,   # ← 신설
) -> None:
    """...
    Source selection:
    - source_bytes (preferred): an in-memory snapshot of the CURRENT document
      (page-management changes already baked in, plaintext). Opened directly;
      `password` is irrelevant. This is what the session passes so reorders/
      deletes/rotations are saved.
    - source_path (legacy/direct callers): re-opens the ORIGINAL file and
      applies operations on top; honors `password` for an encrypted source.
    `encryption` controls the OUTPUT protection independently of either source.
    """
    logger = logger or get_logger()
    document = None
    try:
        if source_bytes is not None:
            document = fitz.open("pdf", source_bytes)
        else:
            document = open_document(source_path, password=password)
        apply_document_operations(document, operations, mode=ApplyMode.SAVE, logger=logger)
        save_kwargs: Dict[str, Any] = {"garbage": 3, "deflate": True}
        if encryption is not None:
            save_kwargs.update(encryption.save_kwargs())
        document.save(output_path, **save_kwargs)
    finally:
        if document is not None:
            document.close()
```

- strict 유지: `source_bytes: bytes | None = None`, `fitz.open` 반환은 기존과 동일 처리.

## 2. M2 — `DocumentSession.save_document`

```python
save_document_copy(
    self.file_path, output_path, self.history,
    logger=logger, encryption=encryption,
    password=self._password,            # source_bytes 경로에선 미사용, 호환 위해 유지
    source_bytes=self.doc.tobytes(),    # ← 현재 doc(페이지 관리 반영) 스냅샷
)
```

- 나머지(재바인드, `is_encrypted` 재계산, history clear, signals)는 불변.
- `self.doc.tobytes()`: 페이지 관리 변형이 반영된 평문 버퍼(probe 확인). history op는 이 버퍼 복사본에만 적용 → `self.doc` 비파괴(미리보기/추가편집 안전).
- `self.file_path`는 여전히 전달하지만 source 결정엔 안 쓰임 — 로그/하위호환 잔존. (제거하면 시그니처 변경 파급이 커서 유지.)

## 3. M3 — 테스트

### `tests/test_page_management.py` (신규)

```
class TestSaveIntegrity:
  test_delete_then_save_persists_deletion
    5p → delete[1,3] → save → 저장파일 page_count==3, 남은 텍스트 P0/P2/P4
  test_reorder_then_save_persists_order
    5p → reorder_pages([2,0,1,3,4]) → save → 저장파일 0번 페이지 "Page 3"(원래 idx2)
  test_rotate_then_save_persists_rotation
    rotate_page(0,90) → save → 저장파일 [0].rotation==90
  test_page_mgmt_and_text_replace_combined
    delete[1] + RedactReplace(p0) → save → 페이지 수 반영 + 교체 텍스트 존재
  test_plain_save_unchanged_when_no_page_mgmt
    텍스트 op만 → save → 기존과 동일(회귀 없음)
```

### `tests/test_open_decrypt.py` (확장)

```
test_encrypted_delete_then_decrypt_save
  암호화 5p 열기 → delete[1] → save(encryption=None) → 저장파일 needs_pass=0,
  page_count==4
test_encrypted_reencrypt_after_page_mgmt
  암호화 열기 → delete[1] → save(EncryptionSettings(user_pw)) →
  저장파일 needs_pass + 새 비번 인증 + page_count==4
```

기존 `test_save_copy_reads_encrypted_source`(source_path 직접 호출)는 하위 호환으로 그대로 통과해야 함.

## 4. 검증 절차

1. `mypy app/pdf_engine.py app/document_session.py` strict 0 에러
2. 신규 테스트 → 전체 스위트(261+)
3. gap-detector → CI green
