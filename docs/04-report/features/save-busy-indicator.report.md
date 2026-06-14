# Save Busy Indicator - Completion Report

> **Summary**: 저장 중 wait 커서 + "저장 중..." 상태 표시로 동기 저장의 "응답 없음" 인상 제거. 풀 async-save(워커)의 큰 위험 대신, 측정 근거로 선택한 경량 안. 매치율 100%, **271 passed**
>
> **Author**: Claude (bkit)
> **Completed**: 2026-06-14
> **Cycle**: save-busy-indicator
> **Match Rate**: 100%

---

## 1. 왜 경량 안인가 (측정 근거)

async-save 착수 전 저장 시간을 측정했다:

| 케이스 | 20p | 100p |
|---|---|---|
| `tobytes()` 직렬화만 | 71ms | 234ms |
| 일반 저장(텍스트+삭제) | 122ms | 710ms |
| RemoveSection 300dpi | 475ms | 880ms |

- **대부분 저장이 1초 미만** — "응답 없음"으로 체감될 건 수백 페이지 + RemoveSection 다수 같은 무거운 경우뿐.
- `tobytes()` 직렬화는 비동기화해도 메인 스레드에 남음(워커는 별도 프로세스라 `self.doc` 공유 불가) → 풀 워커 async-save의 이득이 제한적.
- 풀 async-save는 이 프로젝트의 최고 위험(세션 잠금·재바인드 타이밍·실패 정리·취소·워커 테스트).

→ ROI/위험 비가 가장 좋은 **경량 busy 표시**를 사용자가 선택. 실무에서 저장 지연이 실제 거슬리면 그때 풀 async-save로(`source_bytes` 발판 활용).

## 2. 구현

`file_handlers._commit_save`의 저장 구간(`if output_path:`)을 래핑:
- 저장 직전 `setOverrideCursor(WaitCursor)` + 상태바 `status.saving` + `processEvents()`(커서·메시지 페인트 후 블로킹 저장).
- 성공/실패/예외 무관 `finally: restoreOverrideCursor()` — 영구 wait 커서 방지.
- 기존 성공/에러/취소 메시지·반환값·흐름 전부 불변(들여쓰기만).
- i18n `status.saving`(en/ko). 가짜 진행률(%)은 의도적 배제 — 동기 단일 호출이라 실제 단계가 없음(r7 가짜 진행률 제거 교훈).

## 3. 검증

- 전체 **271 passed** (268 + 신규 3). 저장 UI 경로는 무테스트였는데(전체 검토 M7 공백), 이번에 **커서 복원 회귀 테스트**(성공/실패/취소)를 신설 — 저장 실패 시 wait 커서 영구 잔존이라는 실재 위험을 그물로 고정.
- i18n 281/281. Gap 분석 매치율 100%, 미승인 동작 변경 0(set/restore 1:1, processEvents 1회).

## 4. 다음 (로드맵)

- watermark, text-export-range, pyproject/ruff.
- 풀 async-save는 보류(실무 저장 지연이 실제 거슬릴 때 — `source_bytes` 발판 위에서).
