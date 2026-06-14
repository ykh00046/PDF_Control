# Save Integrity - Completion Report

> **Summary**: 데이터 손실 버그 수정 — 페이지 관리 변경(삭제/회전/이동/복제/병합/재배열)이 저장 시 조용히 손실되던 문제. 저장 source를 원본 재오픈에서 현재 문서 스냅샷으로 전환. 매치율 100%, **268 passed**
>
> **Author**: Claude (bkit)
> **Completed**: 2026-06-14
> **Cycle**: save-integrity
> **Match Rate**: 100%

---

## 1. 발견 경위 (정직성 노트)

async-save 사이클 착수 전 현재 저장 경로를 실측하던 중, **더 심각한 데이터 손실 버그**를 발견해 우선순위를 바꿨다. probe 결과: 5페이지 문서에서 페이지 2개를 삭제하고 저장하면 저장된 파일은 **여전히 5페이지**(원본 그대로)였다.

## 2. 원인

`save_document`가 `save_document_copy(self.file_path, ...)` — 즉 **원본 파일을 다시 열어** history op(텍스트 교체/삭제/크롭)만 적용했다. 페이지 관리는 `self.doc`를 직접 수정할 뿐 history에 안 들어가고 `file_path`도 안 바꾸므로, 저장 시 전부 무시됐다. 단일 저장 경로라 예외 없는 손실이었고, r7-history-policy의 "재배열 시 히스토리 보존"도 무력화하고 있었다(저장하면 재배열 자체가 사라지므로).

## 3. 수정

저장 source를 원본 파일에서 **현재 메모리 문서의 스냅샷**으로 전환:

- `pdf_engine.save_document_copy`에 `source_bytes: bytes | None` 추가 — 있으면 `fitz.open("pdf", source_bytes)`로 열고, 없으면 기존 `open_document(source_path, password)`. **100% 하위 호환**(레거시 직접 호출 불변).
- `DocumentSession.save_document`가 `self.doc.tobytes()`를 전달 — 페이지 관리가 반영된 평문 버퍼(probe: 인증된 암호화 문서도 평문 needs_pass=0). history op redaction은 이 throwaway 버퍼에만 적용되어 `self.doc`는 미리보기/추가편집용으로 무손상.
- 출력 암호화/복호화/재바인드/`is_encrypted` 재계산은 source 선택과 독립이라 불변.

이 `source_bytes` 구조는 다음 async-save 사이클에서 워커 프로세스 입력(`doc.tobytes()`를 워커에 전달)으로 그대로 재사용된다 — 이번 동기 수정이 비동기화의 발판이 된다.

## 4. 검증

- 전체 **268 passed** (261 + 신규 7: 삭제/재배열/회전/페이지관리+텍스트 동시/회귀-무변경 + 암호화 삭제→복호화/재암호화).
- **핵심 회귀 그물**: 저장된 *파일*의 페이지 수·순서·회전을 직접 검증(r7이 놓친 부분 보강).
- mypy strict(pdf_engine + document_session) 0 에러. 4개 회귀 리스크(레거시 경로/doc 비파괴/암호화/password no-op) 갭 분석에서 코드 레벨 안전 확인.

## 5. 다음 (로드맵)

- **async-save** (이번 사이클이 미룬 본래 목표): `source_bytes` 구조 위에서 `tobytes()` 스냅샷을 워커 프로세스에 넘겨 op 적용+저장을 비동기화, 저장 중 UI 블록 해소. 세션 재바인드 연동이 핵심.
- watermark, text-export-range, pyproject/ruff.
