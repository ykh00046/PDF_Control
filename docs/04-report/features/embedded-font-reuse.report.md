# Embedded Font Reuse - Completion Report

> **Summary**: text-fidelity의 후속 — 원본 폰트가 **시스템에 설치되지 않은** 경우 PDF에 임베딩된 폰트 프로그램 자체를 추출·재사용. 충실도 체인의 마지막 단계 완성. 매치율 100%, **261 passed**
>
> **Author**: Claude (bkit)
> **Completed**: 2026-06-13
> **Cycle**: embedded-font-reuse
> **Match Rate**: 100%

---

## 1. 사용자에게 보이는 변화

text-fidelity는 "설치된 폰트"만 매칭할 수 있었다. 이제 **시스템에 없는 서체**(타사 제작 PDF, 특수 폰트)도 PDF 안에 박힌 폰트를 꺼내 교체 텍스트에 그대로 써서 원본 서체를 유지한다. 폰트 해석 우선순위:

1. 사용자가 직접 고른 폰트 (절대 우선)
2. 추출된 원본 폰트명의 시스템 매칭 (text-fidelity)
3. **PDF 임베디드 폰트 재사용** (이번 사이클)
4. Base-14 근사 (최후)

## 2. 구현 요지

- **`fonts.extract_embedded_font(page, source_fontname, must_cover)`**: 페이지 폰트 목록에서 추출 span 폰트명과 basefont를 `_font_name_candidates`로 정규화해 교집합 매칭(span "ArialMT" ↔ basefont "Arial Regular" → 패밀리 "arial"에서 만남), 가장 구체적인 후보를 공유하는 엔트리 우선. `doc.extract_font` → `fitz.Font(fontbuffer=)` 구성 + 글리프 커버리지 검증 통과 시 버퍼 반환.
- **서브셋 폰트 안전 거부**: 서브셋 임베드는 cmap이 제거(Identity-H)돼 `has_glyph`가 전부 0 → 커버리지 검사가 자동 거부(오탐 0). 실측으로 확인하고 테스트로 고정.
- **추출 전 / 등록 후 분리** (구현 중 발견·해결): `apply_redactions`가 남은 텍스트가 참조하지 않는 폰트 리소스를 스트립하므로, redaction 전에 `insert_font`로 등록하면 별칭이 소거돼 "need font file or buffer"로 실패한다. → 추출은 redaction **전**(`_prepare_fonts`, SAVE 모드에서 소스 텍스트 파괴 전 버퍼 확보), 등록은 redaction **후** 신설 `_register_fonts`(Pass 2.5)로 분리.
- **별칭 충돌 방지**: 임베디드 별칭을 버퍼 내용 기반 crc32(`emb{crc32:08x}`)로 — 동일 프로그램은 한 번만 등록·재사용, 서로 다른 프로그램은 충돌 없음. 한 배치에서 여러 다른 폰트를 교체할 때의 잠재 교차오염을 차단(갭 분석 관찰 반영).

## 3. 검증

- 전체 **261 passed** (254 + 신규 7: 추출 성공/미커버 거부/미지폰트 거부/서브셋 거부/미설치 재사용 e2e/서브셋 폴백/별칭 충돌 방지). 전부 Arial 게이트(비Windows·미설치 환경 skip).
- preview=save 등가·사용자 폰트 우선순위 1 보존·기존 system-match 무회귀 모두 갭 분석에서 코드 레벨 확인.
- mypy strict(operations + fonts) 0 에러.

## 4. 충실도 체인 완성

이번 사이클로 "원본과 최대한 유사한 교체"의 폰트 축이 사실상 완결됐다:
**사용자 지정 → 시스템 매칭 → 임베디드 재사용 → Base-14**. 베이스라인 정렬·크기 보존(text-fidelity)과 합쳐, 설치/미설치 무관하게 원본 서체·크기·위치를 유지한다.

## 5. 알려진 한계 / 다음 후보

- 서브셋 임베드 폰트는 cmap 부재로 재사용 불가(안전 폴백) — glyph 재맵핑은 영구 보류(설계 Won't).
- Type3/비추출 폰트는 버퍼 없음 → 자연 스킵.
- 다음 후보: **async-save**(저장 시 동기 적용 한계 — CLAUDE.md Risks), watermark, text-export-range, pyproject/ruff.
