# Ruff Format - Plan + Report (small infra cycle)

> **Summary**: ruff 포매터를 전 코드베이스에 적용하고 CI format 게이트 추가. 동작 불변(토큰 보존). `.git-blame-ignore-revs`로 일회성 대량 diff의 blame 오염 완화. pyproject-ruff에서 "별도 사이클"로 미뤄둔 것
>
> **Author**: Claude (bkit)
> **Created**: 2026-06-15
> **Status**: ✅ Completed (2026-06-15, 동작 불변, 295 passed, ruff format/check 0)
> **Cycle**: ruff-format

---

## 1. 배경 (Why)

pyproject-ruff가 린트(check)만 도입하고 포매터(format)는 "대량 재포맷이라 별도"로 분리. 측정: **75/84 파일 재포맷 대상, ~1600줄 diff**(net −148, 과분할된 코드가 합쳐짐). 동작은 **완전 불변**(ruff format은 토큰 단위 보존, 포맷만) — strict 약화 같은 의미 위험 0.

## 2. 한 일 (What)

### 필수 (Must)

- **M1**: `[tool.ruff.format]` 섹션 명시(기본값: double quote, space indent, line-length 120 [tool.ruff] 따름).
- **M2**: `ruff format app tests scripts main.py` 적용(75파일).
- **M3**: CI(`ci.yml`)에 `ruff format --check` 게이트 추가(check 다음).
- **M4**: `.git-blame-ignore-revs` 생성 — 이 포맷 커밋 해시 등록(후속 커밋)으로 `git blame` 오염 완화. README/문서에 `git config blame.ignoreRevsFile .git-blame-ignore-revs` 안내.
- **M5**: 전체 테스트 통과(동작 불변 확인) + `ruff check` 0 + `ruff format --check` 통과.

### 범위 외 (Won't)

- docstring-code-format(코드 블록 포맷) — 기본 off 유지.
- 공격적 포맷 옵션 변경 — 기본값.

## 3. 검증 (Acceptance)

- [ ] 전체 테스트 295+ 통과 (포맷은 동작 불변).
- [ ] `ruff format --check` 0 (모두 포맷됨).
- [ ] `ruff check` 0 위반 유지.
- [ ] CI format 게이트 추가, green.
- [ ] `.git-blame-ignore-revs`에 포맷 커밋 해시.

## 4. 영향 범위

| 파일 | 변경 |
|---|---|
| `pyproject.toml` | `[tool.ruff.format]` |
| `.github/workflows/ci.yml` | `ruff format --check` 단계 |
| `.git-blame-ignore-revs` | 신규(포맷 커밋 해시) |
| `app/**`, `tests/**`, `scripts/**`, `main.py` | 포맷(동작 불변) |

## 5. 리스크 & 완화

| 리스크 | 완화 |
|---|---|
| 큰 diff로 리뷰/blame 오염 | 동작 불변(format only) → 실질 리뷰 불필요. `.git-blame-ignore-revs`로 blame 완화. 단일 커밋 격리 |
| 포맷이 동작 변경 | ruff format은 토큰 보존, 의미 불변. 전체 테스트가 회귀 그물 |
| 포맷 커밋이 다른 변경과 섞임 | 포맷만 단독 커밋(설정/CI/문서 동반은 무방, 코드 변경 없음) |
