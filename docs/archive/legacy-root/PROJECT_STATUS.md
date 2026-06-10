# Project Status

> **⚠️ DEPRECATED**: This document has been migrated to the new **bkit PDCA** structure.
>
> **See**: [`docs/03-analysis/features/current-state.analysis.md`](docs/03-analysis/features/current-state.analysis.md) for current project status.
>
> **Quick Links**:
>
> - [Documentation Index](docs/_INDEX.md)
> - [Project Configuration](CLAUDE.md)
> - [README](README.md)

---

## 1) Overview

PDF 텍스트 선택 후 삭제/교체/크롭/섹션 이미지화까지 지원하는 데스크톱 앱. PySide6 + PyMuPDF 기반이며 기본 기능은 작동하는 상태.

## 2) Completed

- PDF 열기/저장, Undo/Redo, 선택 기반 삭제·교체, 기본/커스텀 폰트 사용.
- 배치 찾기/교체, 히스토리 패널, 뷰어 줌/이동, i18n(en/ko).
- Crop/섹션 제거(이미지 변환), 로그 출력, 기본 단위 테스트 다수(smoke, undo/redo, remove section, async 렌더 등).

## 3) Known Issues / Risks

- 긴 텍스트가 매우 좁은 영역일 때 8pt까지 축소 후에도 삽입 실패 가능(프리뷰 경고로 안내). 극단적 케이스에서는 영역 확장 또는 고정 폰트 크기 선택 필요.
- 프리뷰/저장 로직은 대부분 일치하지만, 긴 텍스트 축소 실패 시 저장본에서도 글자가 사라질 수 있음(추가 UX 안내/옵션 필요).

## 4) Risks

- 긴 텍스트/좁은 영역 조합에서 축소/미삽입 위험.
- 패키징 시 상대 경로/데이터 번들 미정리로 동결 빌드 실패 가능.

## 5) Next Steps (순서 제안)

1. 긴 텍스트 축소/실패 대응: 고정 폰트 크기 옵션 또는 추가 영역 확장/안내 메시지.
2. 프리뷰·저장 로직 단일화 및 폭 기반 폰트 계산 정교화(이진 탐색 이미 적용, 실패 안내 보강).
3. I18n/QA: 번역 검증 스크립트, 프리뷰=저장 동등성 테스트 추가.
4. Packaging: PyInstaller spec 정리, 경로 헬퍼, 빌드 의존 분리, README/CHANGELOG 업데이트.

문서 상태: 2025-12-16 업데이트.
