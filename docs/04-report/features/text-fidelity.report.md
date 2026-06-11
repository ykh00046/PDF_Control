# Text Fidelity - Completion Report

> **Summary**: 텍스트 교체가 원본의 **서체·크기·베이스라인**을 따라가도록 충실도 개선 — 시스템 폰트 자동 매칭(배치 helv-always 버그 동시 해소), 베이스라인 정렬 삽입, rect 기반 크기 부풀림 제거. 매치율 98→100%, **254 passed**
>
> **Author**: Claude (bkit)
> **Completed**: 2026-06-11
> **Cycle**: text-fidelity
> **Match Rate**: 100% (보강 후)

---

## 1. 사용자에게 보이는 변화

| 항목 | 전 | 후 |
|---|---|---|
| **서체** | 자동 경로는 항상 Helvetica/Times/Courier 근사. **배치 교체는 무조건 Helvetica** | 원본 span의 폰트명을 Windows 설치 폰트에 자동 매칭(예: Calibri→calibri.ttf, 맑은고딕→malgun.ttf). 교체 텍스트의 글리프 커버리지 검증 후 채택 |
| **세로 위치** | 선택 박스 상단 기준 — 폰트 ascender 차이만큼 어긋남 | 원본 첫 줄 **베이스라인에 정확히 안착** (실측: 200.0→200.0) |
| **크기** | 선택 박스를 크게 잡으면 `박스높이×0.6` 하한이 추출값을 덮어써 **글자가 커짐** | 추출된 원본 크기 그대로 (rect 추정은 빈 영역 폴백만) |

## 2. 구현 요지

- **`fonts.py`**: `resolve_pdf_fontname(name, flags, must_cover)` — 서브셋 접두어(`ABCDEF+`) 제거 → 하이픈/camelCase 공백화 → 플래그 스타일 변형 → 패밀리 폴백 순 레지스트리 후보 조회 + `fitz.Font` 글리프 커버리지 검증(Arial에 한글 같은 미스매치 차단). 기존 레지스트리 캐시 인프라 재사용.
- **applicator**: 패스 순서를 메타 추출 → 폰트 해석으로 교정하고 우선순위 체인 확립 — ① `op.fontfile`(사용자 명시, 절대 오버라이드 안 됨) ② 추출 폰트명 시스템 매칭 ③ Base-14 별칭(**추출 메타 기준** — 배치 op의 `helv` 기본값이 별칭을 오염시키던 버그 해소). 해석 결과는 측정·삽입·임베딩에 일관 사용 → preview=save 자동 보장.
- **베이스라인**: span `origin.y`(첫 줄 최솟값)를 `TextMetadata.baseline`으로 추출, 삽입 박스를 `baseline − ascender×최종크기`로 평행이동(축소 폴백 시 최종 크기로 재계산, 페이지 경계 이탈 시 생략).
- **S1**: 단일 교체의 한글 자동 폴백이 일반 맑은고딕보다 **원본 폰트 매칭을 먼저** 시도.

## 3. 검증

- 전체 **254 passed** (235 + 신규 19: 매칭 단위 12 + 충실도 통합 7, Arial 부재 환경 skip 게이트)
- 실측: 교체 결과 ArialMT·10.0pt·베이스라인 200.0 정확 일치
- mypy strict(operations 패키지 + fonts + text_metadata) 0 에러
- Gap 분석 98% → e2e 커버리지 테스트 보강으로 잔여 갭 0. 미승인 동작 변경 0

## 4. 알려진 한계 (의도적 보류)

- **PDF 임베디드 폰트 추출·재사용**(`doc.extract_font`) — 시스템에 없는 폰트까지 커버하는 최종 단계. 서브셋 글리프 커버리지 검사 필요, 후속 사이클 후보.
- 비Windows 매칭(레지스트리 의존) — 캐시 빈 상태로 기존 Base-14 폴백.
- 다중 rect op의 단일 메타 — 기존 한계 유지.

## 5. 다음 (로드맵 후보)

- embedded-font-reuse(임베디드 폰트 재사용), async-save, watermark, text-export-range, pyproject/ruff
