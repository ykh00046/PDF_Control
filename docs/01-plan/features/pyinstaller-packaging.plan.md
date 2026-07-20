# PyInstaller Packaging Plan

> **Status**: Complete
> **Project**: PDF Control
> **Date**: 2026-07-20
> **PDCA Cycle**: pyinstaller-packaging

## 1. Background

패키징은 로드맵(Phase 5)의 유일한 미착수 단계였고, CLAUDE.md Risks에
"Relative path/data bundling not yet tested"로 남아 있었다. spec 파일과
빌드/스모크 스크립트는 이미 존재했지만 **한 번도 실측 검증된 적이 없었다**.
기능이 쌓일수록 frozen 환경 함정(렌더 워커 스폰, i18n 번들, appdata 경로)의
검증 비용이 커지므로 지금 폐쇄한다.

## 2. Requirements

| # | Requirement |
|---|---|
| R1 | `pdf_control.spec`으로 onedir 빌드가 성공한다 |
| R2 | frozen exe의 렌더 워커 경로(`PDF_Control.exe --render-worker`)가 동작한다 |
| R3 | frozen GUI가 기동하고 i18n·config·log가 정상 동작한다 |
| R4 | 빌드/스모크 스크립트가 올바른 인터프리터(3.13)를 사용한다 |
| R5 | 패키징 의존성이 프로젝트 관례대로 `==` 핀된다 |
| R6 | 릴리스 파이프라인(빌드→스모크→zip+SHA256)이 end-to-end 통과한다 |

## 3. Success Criteria

- `scripts/release_windows.ps1` 단일 실행으로 검증된 배포 zip 산출
- 렌더 워커 frozen 스모크 success=true
- GUI 8초 생존 + 로그/설정 파일 격리 appdata에 생성
- 기존 322 테스트 무회귀

## 4. Known Risk (사전 식별)

- `Get-Command python`이 이 머신에서 무관한 3.11 agent venv로 해석됨 →
  잘못된 site-packages로 빌드될 수 있는 조용한 함정. 명시적 해석기 필요.
