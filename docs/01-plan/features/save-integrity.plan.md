# Save Integrity - Plan

> **Summary**: 데이터 손실 버그 수정 — 페이지 관리 변경(삭제/회전/이동/복제/병합/재배열)이 저장 시 손실되던 문제. 저장 source를 원본 파일 재오픈(`self.file_path`)에서 현재 메모리 문서(`self.doc`)의 복사본으로 변경. 동기 유지(async-save는 후속 사이클)
>
> **Author**: Claude (bkit)
> **Created**: 2026-06-14
> **Status**: ✅ Completed (2026-06-14, 매치율 100%, 268 passed)
> **Cycle**: save-integrity

---

## 1. 배경 (Why)

async-save 착수 전 실측에서 **데이터 손실 버그**를 발견했다.

### 증상 (probe 확인)

5페이지 문서에서 페이지 2개를 삭제하고 저장하면 → **저장된 파일은 여전히 5페이지(원본 그대로)**. 페이지 관리 변경이 조용히 사라진다.

### 원인

`DocumentSession.save_document`(document_session.py:146)가 `save_document_copy(self.file_path, ...)` — 즉 **원본 파일을 다시 열어** history op(redact/crop/remove)만 적용한다. 그런데:
- 페이지 관리(`rotate_page`/`delete_pages`/`move_page`/`insert_blank_page`/`duplicate_pages`/`merge_pdfs`/`reorder_pages`)는 `self.doc`를 직접 수정하고 history에 안 들어가며 `file_path`도 안 바꾼다.
- 따라서 저장 시 페이지 관리가 전부 무시된다. 단일 저장 경로(`_commit_save` → `controller.save_document` → `session.save_document`)이므로 예외 없음.

### 부수 영향

r7-history-policy의 가치(재배열 시 히스토리 보존)를 무력화한다 — 저장하면 재배열 자체가 사라지므로. r7 테스트가 `op.page_index`/`session.doc.page_count`만 보고 *저장된 파일*을 검증하지 않아 놓쳤다.

### 실측으로 확정된 수정 방향 (probe)

`self.doc.tobytes()`는 페이지 관리가 반영된 **평문 버퍼**를 준다(암호화 문서도 인증된 상태면 평문, needs_pass=0). 이 버퍼에 history op를 적용해 저장하면 페이지 관리 + 텍스트 op가 **둘 다 보존**되고, destructive redaction은 버퍼 복사본에만 적용되어 `self.doc`는 안전하다.

## 2. 목표 (What)

### 필수 (Must)

- **M1**: `pdf_engine.save_document_copy`에 `source_bytes: Optional[bytes] = None` 추가. 있으면 `fitz.open("pdf", source_bytes)`로 열고(비번 불필요 — 이미 평문), 없으면 기존 `open_document(source_path, password)`. **100% 하위 호환**(기존 source_path 호출 불변).
- **M2**: `DocumentSession.save_document`가 `self.doc.tobytes()`를 `source_bytes=`로 전달. 페이지 관리 + history op가 모두 저장에 반영된다. 출력 보호(`encryption`)·복호화·재바인드 로직은 그대로.
- **M3**: 회귀 테스트 — (a) 페이지 삭제 후 저장 → 저장 파일 페이지 수 = 삭제 반영, (b) 페이지 관리 + 텍스트 교체 동시 → 둘 다 반영, (c) 재배열 후 저장 → **저장 파일의 페이지 순서** 보존(r7 보강), (d) 암호화 문서 페이지 삭제 후 복호화 저장 → 페이지 수 보존 + 평문, (e) 재암호화 라운드트립 유지.

### 권장 (Should)

- **S1**: `save_document_copy` docstring에 source_bytes(현재 doc 상태) vs source_path(원본 재오픈)의 의미 차이 명시.

### 범위 외 (Won't)

- **async-save (워커 분리)** — 별도 사이클. 이번엔 동기 유지(`tobytes()`+op 적용이 메인 스레드). source_bytes 구조가 async-save의 워커 입력과 동일해 다음 사이클에서 그대로 활용.
- 큰 문서의 `tobytes()` 메모리/시간 — async-save에서 다룸.
- 페이지 관리의 undo (여전히 비가역, 기존과 동일).

## 3. 성공 기준 (Acceptance)

- [ ] 전체 테스트 261+ 통과 (신규 회귀 포함).
- [ ] 페이지 삭제/재배열 후 저장 → 저장 파일에 변경 반영(probe로 본 손실 재발 0).
- [ ] 기존 암호화 저장/복호화/재암호화 라운드트립 유지.
- [ ] `save_document_copy(source_path, ...)` 직접 호출 하위 호환(기존 test_open_decrypt 통과).
- [ ] mypy strict(pdf_engine, document_session) 0 에러.
- [ ] Gap 분석 매치율 ≥ 90%.

## 4. 영향 범위 (Scope)

| 파일 | 변경 |
|---|---|
| `app/pdf_engine.py` | `save_document_copy`에 `source_bytes` 추가, source 분기 |
| `app/document_session.py` | `save_document`가 `self.doc.tobytes()` 전달 |
| `tests/test_page_management.py` 또는 신규 | 페이지 관리+저장 회귀 |
| `tests/test_open_decrypt.py` | 암호화 페이지 관리+저장 회귀 |
| `CLAUDE.md` | Resolved 기록 |

## 5. 리스크 & 완화

| 리스크 | 완화 |
|---|---|
| `tobytes()`가 암호화 문서에서 평문 미보장 | probe로 확인(needs_pass=0). 테스트로 고정 |
| 재직렬화로 기존(원본 재오픈)과 미세 바이트 차이 | 내용 동일(텍스트/페이지). 페이지 관리 안 한 경우도 결과 동등 — 전체 스위트로 검증 |
| 암호화 source의 password 인자가 source_bytes 경로에서 무시 | 의도된 동작(버퍼는 이미 평문). source_path 경로는 password 유지(하위 호환) |
| `tobytes()` 메모리(대형 문서) | 이번 범위 외(동기). async-save에서 스트리밍/워커로 |
