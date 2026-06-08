# Replace Wrap Toggle - Plan

> **Summary**: 텍스트 교체 시 "긴 텍스트가 박스를 넘칠 때의 처리 방식(자동 줄바꿈 vs 폰트 축소)"을 전역 상수가 아니라 **교체 단위로 사용자가 선택**할 수 있도록 Replace(배치) 다이얼로그에 토글 UI를 추가
>
> **Author**: Claude (bkit)
> **Created**: 2026-06-08
> **Status**: 🔄 In Progress
> **Cycle**: replace-wrap-toggle

---

## 1. 배경 (Why)

선행 사이클 `text-wrap-replace`(2026-06-02)에서 **긴 텍스트 교체 시 자동 줄바꿈(wrap-first) → 폰트 축소(fallback)** 정책을 구현했다. 그러나 이 정책은 `app/config.py`의 전역 상수 `TEXT_WRAP_ENABLED = True` **하나로만** 제어된다.

`text-wrap-replace.plan.md`의 "범위 외 (Won't — 차기 사이클)" 항목에 다음이 명시돼 있다:

> "Replace 다이얼로그에 사용자 토글 UI 추가 (이번엔 설정 상수 기본 on, UI는 후속)"

즉 본 사이클은 **선행 작업이 의도적으로 미뤄둔 후속 기능**이다.

### 현재 동작의 한계

| 상황 | 현재 | 사용자 니즈 |
|---|---|---|
| 박스를 넘치는 긴 텍스트 교체 | 항상 줄바꿈 우선(전역 on) | 레이아웃 보존을 위해 **이 교체만 폰트 축소**하고 싶을 때가 있음 |
| 표 셀·서명란 등 높이 고정 영역 | 박스가 아래로 확장돼 **다음 행 침범** 가능 | 줄바꿈 대신 한 줄 유지(축소) 선택 필요 |
| 제어 수단 | 코드 상수 수정뿐 (재빌드 필요) | 다이얼로그에서 즉시 선택 |

`fixed_font` 체크박스는 이미 교체 단위 옵션 전달 경로(`replacements_confirmed` → `RedactReplace`)를 입증했다. 동일 패턴으로 wrap 옵션을 얹는 것이 자연스럽다.

> **정직성 노트**: 백엔드 줄바꿈 로직(`_insert_text_with_autofit`)은 이미 완성돼 있다. 본 사이클은 **새 동작을 만들지 않고**, 기존 동작의 on/off를 교체 단위로 노출하는 "제어권 이양"에 집중한다. 과대포장하지 않는다.

---

## 2. 목표 (What)

### 필수 (Must)
- **M1**: `BatchReplaceDialog`에 "긴 텍스트 자동 줄바꿈" 체크박스 추가 (기본 체크 = 현 전역 동작과 동일).
- **M2**: 체크 해제 시 해당 교체는 **줄바꿈을 건너뛰고 폰트 축소 폴백**으로만 처리된다.
- **M3**: 선택값이 `RedactReplace`까지 전달되어 `applicator`가 교체별로 wrap 여부를 적용한다.
- **M4**: 미지정(`None`) 시 기존 전역 `TEXT_WRAP_ENABLED`를 따른다 — **100% 하위 호환**.

### 권장 (Should)
- **S1**: 모든 신규 UI 문자열을 i18n(en/ko) 키로 추가, 누락 0.
- **S2**: 체크박스에 동작 설명 툴팁 제공.

### 범위 외 (Won't)
- 단일 선택 교체(`replace_selection`, 단순 입력 프롬프트) — 풍부한 옵션 UI가 없어 이번 범위 제외. wrap 인자는 `None`(전역 따름)으로 유지.
- 줄 간격/최대 확장 비율의 UI 노출 (상수 유지).
- 양쪽 정렬·하이픈네이션.

---

## 3. 성공 기준 (Acceptance)

- [ ] 기존 전체 테스트 통과 유지 (회귀 0).
- [ ] **신규 테스트**: `RedactReplace(wrap=False)` + 좁은 박스 + 긴 텍스트 → 줄바꿈 없이 **폰트 축소**(`text.shrunk`) 발생.
- [ ] **신규 테스트**: `RedactReplace(wrap=True)` → 다중 라인 수용(`text.wrapped`), 기존 동작과 동일.
- [ ] **신규 테스트**: `RedactReplace(wrap=None)` → 전역 `TEXT_WRAP_ENABLED` 따름(하위 호환).
- [ ] i18n 검증 통과(en/ko 키 동수, 플레이스홀더 일치).
- [ ] Gap 분석 매치율 ≥ 90%.

---

## 4. 영향 범위 (Scope)

| 파일 | 변경 |
|---|---|
| `app/operations/redact.py` | `RedactReplace.__init__`에 `wrap: Optional[bool] = None` 추가, `to_dict` 반영 |
| `app/operations/applicator.py` | op별 wrap 해석 → `_insert_replacement_text` → `_insert_text_with_autofit(wrap_enabled)` 스레딩 |
| `app/batch_replace_dialog.py` | "자동 줄바꿈" 체크박스 추가, emit dict에 `wrap` 포함 |
| `app/handlers/dialog_handlers.py` | `process_batch_replacements`에서 `wrap` 읽어 `RedactReplace`에 전달 |
| `app/i18n/en.json`, `ko.json` | `batch.use_wrap`, `batch.use_wrap.tooltip` 키 |
| `tests/test_text_wrap.py` (또는 신규) | wrap True/False/None 분기 테스트 |

---

## 5. 리스크 & 완화

| 리스크 | 완화 |
|---|---|
| applicator 시그니처 변경이 다른 호출부 깨뜨림 | `_insert_text_with_autofit`에 `wrap_enabled` **키워드 기본값** 부여, 기존 호출 무영향 |
| 직렬화(to_dict) 하위 호환 | `wrap` 키 추가만, 기존 키 불변 |
| 전역 상수와 혼동 | `None`=전역 따름, `True/False`=명시 override로 우선순위 명확화 |
