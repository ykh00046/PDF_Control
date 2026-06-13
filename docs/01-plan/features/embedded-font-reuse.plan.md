# Embedded Font Reuse - Plan

> **Summary**: text-fidelity의 후속 — 원본 폰트가 시스템에 **설치되지 않은** 경우, PDF에 임베딩된 폰트 프로그램 자체를 추출해 교체 텍스트에 재사용 (글리프 커버리지 검증 포함). 충실도 체인의 마지막 단계
>
> **Author**: Claude (bkit)
> **Created**: 2026-06-11
> **Status**: ✅ Completed (2026-06-13, 매치율 100%, 261 passed)
> **Cycle**: embedded-font-reuse

---

## 1. 배경 (Why)

text-fidelity(2026-06-11)로 설치 폰트 자동 매칭은 해결됐지만, **시스템에 없는 폰트**의 문서(타사 제작 PDF, 특수 서체)는 여전히 Base-14 폴백이다. PDF에는 대개 폰트 프로그램이 임베딩돼 있으므로 그것을 꺼내 쓰면 설치 여부와 무관하게 원본 서체를 유지할 수 있다.

### 2026-06-11 실측 (probe — 설계 확정 근거)

| 가정 | 결과 |
|---|---|
| `doc.extract_font(xref)` → 사용 가능한 폰트 버퍼 | ✅ 전체 임베딩 ttf 1MB 추출, `fitz.Font(fontbuffer=)` 구성·측정 정상 |
| `page.insert_font(fontbuffer=)` 등록 후 **별칭만으로** `insert_textbox` | ✅ 렌더 성공 (ArialMT 10pt, 임시파일 불필요) |
| 서브셋 폰트 재사용 | ⚠️ `subset_fonts()` 결과물은 cmap 제거(Identity-H)로 `has_glyph`가 **전부 0** → 커버리지 검사가 자연 거부. **오탐 없음** — 서브셋 문서는 안전하게 폴백 |
| 식별자 일치 | ⚠️ span 폰트명(`ArialMT`) ≠ basefont(`Arial Regular`) — 패밀리 정규화 매칭 필요 (`_font_name_candidates` 재사용) |

## 2. 목표 (What)

### 필수 (Must)

- **M1**: `fonts.py`에 `extract_embedded_font(page, source_fontname, must_cover) -> Optional[bytes]` 신설 — 페이지 폰트 목록에서 추출 폰트명과 **후보 교집합**(기존 `_font_name_candidates` 재사용, 구체적 후보 우선)으로 매칭 → `extract_font` → `fitz.Font(fontbuffer=)` 구성 + 글리프 커버리지 검증 통과 시 버퍼 반환. 실패·서브셋·미커버 → None.
- **M2**: applicator 폰트 우선순위 체인 확장 — ① `op.fontfile`(사용자) ② 시스템 매칭 ③ **임베디드 재사용** ④ Base-14. resolved 튜플을 `(alias, fontfile, fontbuffer)`로 확장, 측정(`fitz.Font(fontbuffer=)`)·등록(`insert_font(fontbuffer=)`)·삽입(별칭 참조) 일관 적용. preview=save는 단일 경로로 자동 보장.
- **M3**: 테스트 — 전체 임베딩 재사용 성공(시스템 매칭을 None으로 모킹해 "미설치" 시뮬레이션, 서체·베이스라인·크기 유지), 서브셋 문서 안전 폴백(크래시 없이 Base-14), 한글 must_cover 거부, 폰트명 불일치 시 None.

### 권장 (Should)

- **S1**: 임베디드 재사용 채택 시 debug 로그(어느 xref/basefont를 재사용했는지) — 진단성.

### 범위 외 (Won't)

- 서브셋 폰트의 글리프 재맵핑/병합 — cmap 부재로 안전 판정 불가, 영구 보류(커버리지 검사가 자동 거부).
- 임베디드 폰트의 디스크 캐싱 — 페이지 단위 인메모리 처리로 충분.
- Type3/비추출(`n/a`) 폰트 — 버퍼 없음 → 자연 스킵.

## 3. 성공 기준 (Acceptance)

- [ ] 전체 테스트 254+ 통과.
- [ ] 시스템 매칭 불가 상황에서 전체 임베딩 원본 폰트로 교체 렌더(span 폰트 = 원본 계열), 베이스라인·크기 유지.
- [ ] 서브셋 문서: 재사용 미채택 + 정상 폴백(예외 0).
- [ ] mypy strict(fonts, operations 게이트) 0 에러.
- [ ] Gap 분석 매치율 ≥ 90%.

## 4. 영향 범위 (Scope)

| 파일 | 변경 |
|---|---|
| `app/fonts.py` | `extract_embedded_font` + 커버리지 헬퍼 분리(`_font_covers`) |
| `app/operations/applicator.py` | resolved 튜플 3원소화, 체인 ③ 추가, 버퍼 기반 측정/등록/삽입 |
| `tests/test_text_fidelity.py` 또는 신규 | M3 테스트 |

## 5. 리스크 & 완화

| 리스크 | 완화 |
|---|---|
| 잘못된 폰트 매칭(동일 패밀리 다른 스타일) | 후보 교집합의 **가장 구체적**(인덱스 최소) 후보 기준 선택 + 커버리지 검사. 스타일 오차여도 시각적 근접 — Base-14보다 우월 |
| insert_textbox가 별칭 못 찾음 | 실측 검증 완료(probe). 등록 실패 시 기존 임베딩-실패 폴백(Base-14) 경로 재사용 |
| 대형 폰트 버퍼 메모리 | 페이지당 적용 시점에만 보유, op 수만큼 — 전형적 문서에서 수 MB 수준. 렌더 워커는 프로세스 종료로 회수 |
| strict 게이트(fonts는 warn_return_any 완화 없음) | fitz 반환을 `bytes()` 명시 변환 |
