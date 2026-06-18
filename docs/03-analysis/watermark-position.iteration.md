# PDCA Iteration Report: watermark-position

## Overview

| Item | Value |
|---|---|
| Date | 2026-06-19 |
| Total Iterations | 1 |
| Initial Match | 92% |
| Final Match | 100% |
| Final Status | Success |

## Iteration 1

- [Important] 이미지 90° 회전의 점유 영역을 회전 bounding box로 중복 계산
  - 위치: `app/operations/watermark.py`
  - 수정: PyMuPDF target rect 자체는 회전하지 않는 계약에 맞춰 원본 target 크기로 중심 계산
- [Important] 이미지 Dialog와 Controller의 위치 전달 테스트 공백
  - 위치: `tests/test_watermark.py`
  - 수정: Controller history, Dialog payload/tile enabled, 0°/90° 36pt 여백 테스트 추가

## Score Progression

| Iteration | Structural | Functional | Contract | Runtime | Overall |
|---|---:|---:|---:|---:|---:|
| Initial | 100 | 90 | 90 | 90 | 92 |
| Final | 100 | 100 | 100 | 100 | 100 |

## Result

모든 식별 gap을 1회 반복에서 해결했으며 잔여 이슈가 없다.
