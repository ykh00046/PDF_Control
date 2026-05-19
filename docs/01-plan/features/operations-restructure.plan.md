# Plan: operations-restructure

**Status**: Plan
**Date**: 2026-04-21
**Owner**: PDF Control
**Priority**: Medium (quality/maintainability, no user-facing defect)
**Inspiration**: rhwp `src/document_core/` CQRS + command module split, `validation.rs` `ValidationReport.summary()` 패턴

## Problem

두 가지 구조적 부채가 축적되고 있다:

1. **`app/operations_service.py`가 563줄로 비대화.**
   - `OperationApplicator` 하나에 Pass 0~4(crop / font prep / clear / text insert / section removal)의 mode-aware 로직이 전부 집중.
   - 새 연산을 추가하려면 이 파일을 계속 수정해야 함 (SRP 위반 조짐).
   - mypy strict 범위(`mypy.ini`)가 이 단일 파일에 묶여 있어, 분할 시 재설계 필요.

2. **`OpWarning` 소비 측이 경고 카운팅을 매번 수동 구현.**
   - `ApplyResult.font_size_adjustments`, `text_shrink_count` 같은 property가 코드별로 하드코딩.
   - `app/model.py:395`, `app/ui.py:162` 등에서 OpWarning list를 직접 순회해 필터링.
   - 새 `code`(예: `"text.overflow"`, `"image.dpi_capped"`)가 추가될 때마다 property/순회 로직을 다시 써야 함.

## Goal

1. **`app/operations/` 패키지로 분할**해 각 연산 타입이 독립 모듈로 서식.
2. **`WarningReport` 집계 API**(`summary()`, `by_kind(code)`, `has(code)`)를 `operations_service.py`에 도입, UI/model 소비 측을 단순화.
3. **외부 동작은 100% 동일** — 리팩토링만. 회귀 없음, 테스트 100/100 유지.

## Non-Goals

- `DocumentSession` (`app/model.py`) 자체 분할 — 별도 사이클.
- CQRS 레벨 Commands/Queries 완전 분리 — 지금은 시기상조.
- 새 연산 타입 추가.
- UI 레이어 변경 (소비 측은 리팩토링만).

## Acceptance Criteria

- [ ] `app/operations/` 패키지 생성, `__init__.py`에서 기존 `operations_service` public API (`OperationApplicator`, `ApplyMode`, `ApplyResult`, `OpWarning`, `TextMetadata`)를 동일한 symbol로 re-export
- [ ] 하위 모듈 분할:
  - `applicator.py` — `OperationApplicator` 오케스트레이션
  - `passes.py` — Pass 0~4 구현 (또는 `crop.py`/`text_edit.py`/`remove_section.py`로 추가 분할)
  - `warnings.py` — `OpWarning`, `WarningReport`, `ApplyResult`
  - `types.py` — `ApplyMode`, `TextMetadata`
- [ ] `WarningReport.summary() -> Dict[str, int]` — code별 카운트 집계
- [ ] `WarningReport.by_kind(code: str) -> List[OpWarning]` — 종류별 필터
- [ ] `WarningReport.has(code: str) -> bool` — 단축 판정
- [ ] `ApplyResult.font_size_adjustments` / `text_shrink_count` 는 **새 API로 위임** (backward compat 유지, 본체는 삭제)
- [ ] `app/model.py:395`, `app/ui.py:162` 등 기존 수동 순회 코드가 `WarningReport` API 사용으로 전환
- [ ] `mypy.ini`의 strict scope가 `app.operations` 패키지 전체로 확장
- [ ] `scripts/check_claude_md_drift.py` / `docs/_resolved.yml` 정합성 유지
- [ ] 전체 회귀 테스트 100/100 유지 (신규 unit test 추가 후 최소 103)
- [ ] PyInstaller onedir 빌드 정상 (import 경로 변경 확인)

## Affected Files

**Source 이동/분할:**
- `app/operations_service.py` (563줄) → `app/operations/` 패키지로 분할
  - 분할 후 원 파일은 **deprecation shim**으로 유지 (한 사이클 동안, public symbol re-export만)
- `app/model.py` — `from app.operations_service import ...` → `from app.operations import ...`
- `app/ui.py` — 동일
- `app/controller.py`, `app/render_worker.py`, `app/viewer.py` — import 갱신

**설정/빌드:**
- `mypy.ini` — `[mypy-app.operations_service]` → `[mypy-app.operations.*]`
- PyInstaller spec (있다면) — hidden imports 확인

**테스트:**
- `tests/test_operations.py` — import 경로 갱신
- `tests/test_warning_report.py` (신규) — `summary()` / `by_kind()` / `has()` 단위 테스트
- 기존 `tests/test_long_text_warning.py` — `WarningReport` API 사용으로 리팩토링

**문서:**
- `CLAUDE.md` "Source Boundary" / "Project Structure" 섹션 갱신
- `docs/_INDEX.md` — plan/design/analysis/report 4건 추가
- `docs/02-design/features/unified-operations.design.md` — "superseded by operations-restructure" 주석 링크

## Test Strategy

1. **회귀 우선** — 리팩토링 전 100/100 스냅샷, 각 커밋마다 전체 테스트 실행.
2. **Unit (신규)** — `WarningReport`:
   - 빈 리포트: `summary() == {}`, `has("x") == False`
   - 다중 code 혼합: `summary()["text.shrunk"] == 3`, `by_kind("text.overflow")` 정확 필터
   - `ApplyResult.text_shrink_count` 가 `report.summary().get("text.shrunk", 0)`와 일치
3. **Import 호환** — 한 테스트가 `from app.operations_service import OperationApplicator` 로 여전히 import 가능함을 검증 (shim 유지 확인).
4. **mypy strict** — `mypy app/operations/` 무에러.
5. **E2E 수동** — PySide6 앱 기동, Replace / RemoveSection / Crop 각각 preview+save 한 번씩 실행해 경고/상태바 동작 동일 확인.

## Risks

- **Import 경로 변경이 숨은 모듈에 파급** — `__pycache__` 잔재, 외부 스크립트, PyInstaller hidden imports.
  - **완화**: deprecation shim을 한 사이클 유지, `grep -r operations_service` 전수 스캔.
- **mypy strict 범위 확장 시 신규 에러 노출** — 다른 파일 끌어들이며 숨은 타입 문제 드러날 수 있음.
  - **완화**: `follow_imports=silent`를 `app.operations.*`에도 동일 적용, 패키지 외부로 확산 금지.
- **`ApplyResult` property 제거 시 외부 코드 breakage** — 테스트/UI가 직접 참조 중.
  - **완화**: property는 `WarningReport`로 위임하되 **남긴다** (backward compat). 내부 구현만 교체.
- **리팩토링 범위 팽창** — 분할 중 "이왕 이렇게 된 거"가 등장할 위험.
  - **완화**: Non-Goals 섹션을 엄격히 지킨다. 별도 이슈로 기록.

## Open Questions

1. **분할 입도**: `passes.py` 단일 vs `crop.py`/`text_edit.py`/`remove_section.py` 3분할 — 각 Pass의 결합도 조사 후 Design 단계에서 결정.
2. **`ApplyResult` vs `WarningReport`**: `WarningReport`를 `ApplyResult.report: WarningReport` 로 embed할지, `ApplyResult` 자체가 `WarningReport`를 상속할지 — Design에서 확정.
3. **Deprecation shim 유지 기간**: 1 사이클? 2 사이클? → 기본 "다음 release까지".
4. **`OperationApplicator.current_warnings` 내부 상태**: stateless를 표방하면서 인스턴스 변수로 누적 중 (line 131). 이번에 함께 정리할지 Non-Goal로 둘지.

## Next Phase

`/pdca design operations-restructure` — 패키지 레이아웃 확정 (Open Questions 1~2), 각 Pass의 의존성 그래프 작성, deprecation shim 구체안.
