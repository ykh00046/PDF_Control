# Text Fidelity - Plan

> **Summary**: 텍스트 교체 충실도 개선 — (M1) 추출된 원본 폰트명을 시스템 폰트에 자동 매칭(기존 `fonts.py` 인프라 연결), (M2) 베이스라인 정렬 삽입, (M3) fontsize 추출값을 rect 하한이 덮어쓰는 동작 수정
>
> **Author**: Claude (bkit)
> **Created**: 2026-06-11
> **Status**: ✅ Completed (2026-06-11, 매치율 100%, 254 passed)
> **Cycle**: text-fidelity

---

## 1. 배경 (Why)

"원본 폰트·크기·위치와 최대한 유사하게 교체"가 목표인데, 2026-06-11 분석에서 충실도 손실 지점 3곳을 확인:

1. **폰트 — Base-14 강등**: `_extract_text_metadata`가 원본 span의 폰트명을 추출하지만, 자동 경로는 `_base14_font_alias`로 Helvetica/Times/Courier 3계열 근사로 강등된다. `fonts.py`에 Windows 레지스트리 기반 `get_font_path_by_name()`이 이미 있는데 **자동 연결이 안 돼 있다**. 더 나쁘게, **배치 교체는 op가 `fontname="helv"` 기본값으로 생성**되고 `_prepare_fonts`는 op.fontname만 보므로(추출 메타는 별칭 폴백에만 사용) 배치 교체는 사용자가 폰트를 수동 선택하지 않는 한 **항상 helv**다.
2. **위치 — 베이스라인 무시**: `insert_textbox(선택박스+패딩)`은 박스 상단 기준 배치. span dict에 베이스라인(`origin`)이 있는데 추출에서 버린다. 폰트가 다르면 ascender 차이만큼 세로 어긋남.
3. **크기 — rect 하한이 추출값을 덮어씀**: `metadata["fontsize"] = max(평균, rect높이*0.6)` (`text_metadata.py:49`) — 선택 박스를 크게 잡으면 9pt 원본이 더 큰 폰트로 교체된다. rect 기반 추정은 span이 없을 때의 폴백이어야 한다.

## 2. 목표 (What)

### 필수 (Must)

- **M1 (폰트 자동 매칭)**: `fonts.py`에 `resolve_pdf_fontname(pdf_fontname, font_flags=0) -> Optional[str]` 신설 — 서브셋 접두어(`ABCDEF+`) 제거, 하이픈/camelCase → 공백 변형, 스타일 접미어/플래그 조합, 패밀리 폴백 순으로 레지스트리 캐시 조회. applicator의 폰트 결정을 **메타데이터 인지형 우선순위 체인**으로 교체: ① `op.fontfile`(사용자 명시) → ② 추출 폰트명의 시스템 매칭 → ③ Base-14 별칭(추출 폰트명 기준 — 배치 op의 helv 기본값 대신). 매칭된 폰트는 측정(`fitz.Font`)·삽입·임베딩에 일관 사용 — preview=save 동일성은 applicator 단일 경로로 자동 보장.
- **M2 (베이스라인 정렬)**: `_extract_text_metadata`가 교차 span의 베이스라인(`origin.y` 최솟값 = 첫 줄)을 `baseline`으로 추출(`TextMetadata`에 `Optional[float]` 추가). applicator가 삽입 박스 y0를 `baseline - ascender × 최종 fontsize`로 보정(축소 시 최종 크기로 재계산, baseline 부재/폰트 측정 실패 시 기존 배치 그대로).
- **M3 (크기 신뢰)**: span 추출값이 있으면 그대로 사용. rect 기반 추정(0.6 비율, 8..72 클램프)은 **span 부재 폴백으로만**.

### 권장 (Should)

- **S1**: 단일 교체의 한글 자동 폴백(`_resolve_replacement_font`)이 일반 맑은고딕 기본값보다 **추출 폰트명 매칭을 먼저** 시도 (원본이 바탕이면 바탕으로).

### 범위 외 (Won't)

- PDF 임베디드 폰트 추출·재사용(`doc.extract_font`) — 서브셋 글리프 커버리지 검사 필요, 후속 사이클.
- 자간/장평 보정(TextWriter), 다중 rect별 개별 메타 — 기존 한계 유지.
- 비Windows 폰트 매칭 — 캐시 빈 상태로 기존 Base-14 폴백(현행 동일).

## 3. 성공 기준 (Acceptance)

- [ ] 전체 테스트 235+ 통과.
- [ ] **통합 테스트**: Arial로 작성된 PDF의 텍스트를 (수동 폰트 선택 없이) 교체 → 저장 결과의 해당 span 폰트가 Arial 계열(helv 아님). 시스템에 Arial 부재 시 skip.
- [ ] **베이스라인 테스트**: 교체 후 새 span의 `origin.y`가 원본과 ±1pt 이내.
- [ ] **M3 테스트**: 원본 글자보다 큰 선택 박스에서도 추출 fontsize 유지(rect 하한 미적용), span 부재 시 rect 폴백 유지.
- [ ] 폰트명 후보 생성 단위 테스트(서브셋/하이픈/camelCase/스타일/패밀리).
- [ ] mypy strict(fonts, text_metadata, operations 게이트) 0 에러.
- [ ] Gap 분석 매치율 ≥ 90%.

## 4. 영향 범위 (Scope)

| 파일 | 변경 |
|---|---|
| `app/fonts.py` | `resolve_pdf_fontname` + 후보 생성 헬퍼 (strict 유지) |
| `app/text_metadata.py` | M3 크기 수정 + `baseline` 추출 |
| `app/operations/types.py` | `TextMetadata.baseline: Optional[float]` |
| `app/operations/applicator.py` | 메타 인지형 폰트 해석 체인 + 베이스라인 보정 |
| `app/handlers/edit_handlers.py` | S1 우선순위 |
| `tests/test_text_fidelity.py` | 신규 |
| `tests/test_fonts*.py` 또는 신규 | 후보 생성/매칭 단위 테스트 |

## 5. 리스크 & 완화

| 리스크 | 완화 |
|---|---|
| 시스템 매칭 폰트로 글리프 누락(예: Arial에 한글) | `fitz.Font.has_glyph`? — 범위 제한: 교체 텍스트에 매칭 폰트가 글리프를 못 가지면 기존 한글 폴백·Base-14 경로가 이미 동작. M1 매칭 결과는 `fitz.Font(fontfile)` 구성 성공 + 텍스트 글리프 검사 통과 시에만 채택 |
| 베이스라인 보정이 기존 배치와 크게 달라짐 | 보정은 ascender 차이 수준(보통 ≤1-2pt). baseline 부재·측정 실패 시 기존 동작. 기존 wrap/warning 테스트가 회귀 그물 |
| M3 변경이 기존 테스트 가정 깨뜨림 | rect 하한에 의존하는 단언 없음(사전 grep) — 전체 스위트로 검증 |
| 레지스트리 조회 비용 | `fonts.py` 캐시(1회 스캔) 기존 인프라 그대로 |
