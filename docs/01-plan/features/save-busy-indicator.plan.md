# Save Busy Indicator - Plan (design integrated)

> **Summary**: 저장 중 busy 표시 — wait 커서 + 상태바 "저장 중..." 으로 동기 저장의 "응답 없음" 인상 제거. 측정상 대부분 저장이 1초 미만이라 풀 async-save(워커) 대신 선택한 경량 안. 워커 없음, 위험 최소
>
> **Author**: Claude (bkit)
> **Created**: 2026-06-14
> **Status**: ✅ Completed (2026-06-14, 매치율 100%, 271 passed)
> **Cycle**: save-busy-indicator

---

## 1. 배경 (Why)

async-save 착수 전 저장 시간을 실측: 20p 일반 122ms / 100p 일반 710ms / 100p RemoveSection 300dpi 880ms. **대부분 1초 미만**이고, `tobytes()` 직렬화(234ms@100p)는 비동기화해도 메인 스레드에 남아 워커 분리의 이득이 제한적. 풀 async-save는 이 프로젝트에서 가장 위험한 작업(세션 잠금·재바인드 타이밍·실패 정리·취소·워커 테스트)이라, ROI/위험 비가 가장 좋은 **경량 busy 표시**를 사용자가 선택.

목적: 저장이 길어질 때(수백 페이지 + RemoveSection) "응답 없음" 인상만 제거. 실제 블록은 유지하되 사용자가 "처리 중"임을 인지.

## 2. 목표 (What)

### 필수 (Must)

- **M1**: `file_handlers._commit_save`의 저장 구간을 busy 표시로 감싼다 — 저장 직전 `QApplication.setOverrideCursor(Qt.WaitCursor)` + 상태바 `tr("status.saving")` + `QApplication.processEvents()`(커서·메시지 페인트 후 블로킹 저장). 저장 성공/실패/예외 무관하게 **`finally`에서 `restoreOverrideCursor()`** — 영구 wait 커서 방지.
- **M2**: i18n `status.saving` 키 추가(en/ko). 기존 성공/취소/에러 메시지·반환값·흐름 전부 불변.

### 권장 (Should)

- **S1**: 커서 복원 회귀 테스트 — 저장 성공/실패 두 경로 모두 호출 후 `QApplication.overrideCursor() is None`.

### 범위 외 (Won't)

- 워커/스레드 백그라운드 저장(풀 async-save) — 보류. 실무에서 저장 지연이 실제 거슬리면 그때.
- 진행률 바(%) — 동기 단일 호출이라 실제 단계 진행률 없음(r7에서 가짜 진행률 제거한 교훈). busy 커서/메시지만, 가짜 % 금지.
- 메뉴/버튼 비활성화 — 동기 블록 중 입력은 큐잉되며, 단일 저장 호출엔 과함. 커서로 충분.

## 3. 설계 (Design)

`_commit_save`의 `if output_path:` 블록(file_handlers.py:149-180):

```python
if output_path:
    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    self.statusBar().showMessage(tr("status.saving"))
    QApplication.processEvents()  # paint cursor + message before the blocking save
    try:
        self.controller.save_document(output_path, encryption=encryption)
        ... existing success path (status, title, last_dir, return True) ...
    except Exception as e:
        ... existing error path (log, QMessageBox.critical, return False) ...
    finally:
        QApplication.restoreOverrideCursor()
```

- import 추가: `from PySide6.QtCore import Qt`, `QApplication`을 QtWidgets import에 추가.
- `processEvents()`는 **저장 전 1회만** — 커서/메시지를 그리기 위함. 저장 자체는 그대로 동기 블록.
- `restoreOverrideCursor`는 `setOverrideCursor`와 1:1. 성공/취소-아닌-실패/예외 모두 `finally`로 보장.
- 취소(output_path 없음) 경로는 setOverrideCursor 진입 전이라 복원 불필요.

## 4. 성공 기준 (Acceptance)

- [ ] 전체 테스트 268+ 통과.
- [ ] 저장 성공/실패 모두 후에 `overrideCursor()` 복원(None).
- [ ] i18n en/ko 동수 + `status.saving` 존재.
- [ ] 기존 저장 동작(성공 메시지/타이틀/last_dir/암호화/복호화) 불변.
- [ ] Gap 분석 매치율 ≥ 90%.

## 5. 영향 범위 (Scope)

| 파일 | 변경 |
|---|---|
| `app/handlers/file_handlers.py` | `_commit_save` busy 래핑 + import |
| `app/i18n/en.json`, `ko.json` | `status.saving` |
| `tests/test_save_busy.py` | 신규 — 커서 복원 회귀 |

## 6. 리스크 & 완화

| 리스크 | 완화 |
|---|---|
| 예외 시 wait 커서 영구 잔존 | `finally` 복원 — 테스트로 고정 |
| processEvents가 재진입(저장 중 다른 이벤트) 유발 | 저장 *전* 1회만 호출(블로킹 저장 중엔 호출 안 함) — 재진입 없음 |
| setOverrideCursor 중첩 누적 | _commit_save는 단일 진입, 중첩 없음. 1:1 보장 |
