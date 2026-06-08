# R2 Quality Fixes - Analysis (Check)

> **Summary**: 설계(Design) 대비 구현(Do) 정합성 분석 및 검증 결과
>
> **Author**: Claude (bkit)
> **Created**: 2026-06-02
> **Status**: ✅ Approved
> **Design**: [r2-quality-fixes.design.md](../../02-design/features/r2-quality-fixes.design.md)

---

## 1. Match Rate

| 항목 | 설계 | 구현 | 정합 |
|------|------|------|------|
| M1 get_text_length 교체 | fitz.Font.text_length, 루프 밖 1회 생성 | 동일 적용 | ✅ |
| M2 11개 테스트 그린 | 11개 복구 | 11개 복구 + 1개 설계갭 수정 | ✅ |
| M3 leaf strict 게이트 | config/logger/path_helper/text_utils | 4개 모두 strict | ✅ |
| S1 text_metadata/fonts | 소규모 수정 후 추가 | 추가 완료 | ✅ |
| S2 preview=save 회귀검증 | 통과 유지 | 통과 | ✅ |
| #3 DRY 회귀 | 단일 경로 보존 | 회귀 없음 | ✅ |

**Match Rate: 100%** (Must 3 + Should 2 + 검증 1 전부 충족)

---

## 2. 설계와의 차이 (정직성 기록)

### 2.1 mypy 사전측정 오염 (설계 가정 오류 → 실측으로 정정)

설계 문서 §2.2는 `config`·`logger`·`path_helper`를 **0 strict 에러**로 기재했으나, 이는 **당시 `mypy.ini`의 `ignore_errors = True`가 적용된 상태에서 측정**된 오염값이었다. 게이트 활성화 후 실제 에러:

| 모듈 | 설계 가정 | 실제 strict 에러 | 조치 |
|------|-----------|------------------|------|
| config | 0 | 1 (Dict type-arg) | 수정 |
| logger | 0 | 7 (annotation·handler 타입) | 수정 |
| path_helper | 0 | 1 (`sys._MEIPASS` attr) | `type: ignore` |
| text_utils | 0 | 0 | — |

→ 총 10개 에러를 모두 수정하여 **6개 모듈 전부 strict 0 에러 달성**. 설계 예측은 틀렸으나 결과는 목표를 초과 달성.

### 2.2 M1에서 발견된 설계 갭 (보너스 수정)

API 교체 후 autofit이 **정상 작동**하면서 `test_narrow_rect_long_text_emits_shrink_warning`이 노출한 잠재 버그: **autofit 바이너리서치로 폰트를 축소해 맞춘 경우 `text.shrunk` 경고가 누락**(폴백 경로에서만 emit). 

수정: ① initial 크기에서 안 맞을 때만 축소(시각적 동등성 보존) ② autofit 축소 시 `text.shrunk` 경고 emit. 이는 기존 버그(get_text_length가 항상 예외→경고 누락 또는 오작동)에 가려져 있던 실질 결함.

---

## 3. 검증 증거

```
# 전체 테스트
128 passed in 8.75s          # 이전: 11 failed, 116 passed (+ 신규 게이트 테스트 1)

# mypy strict 게이트
leaf modules:    Success: no issues found in 6 source files
operations pkg:  Success: no issues found in 8 source files
test_mypy.py:    2 passed
```

---

## 4. 잔여 항목 (차기 사이클)

- `document_session`(16 strict 에러), `model`, `pdf_engine` → `/pdca plan typing-legacy-core`
- 신규 기능 큐(page-undo-redo 등)는 별도 사이클 유지
