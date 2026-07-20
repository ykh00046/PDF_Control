# PyInstaller Packaging Completion Report

> **Status**: Complete
> **Project**: PDF Control
> **Completion Date**: 2026-07-20
> **PDCA Cycle**: pyinstaller-packaging

## 1. Executive Summary

기존 spec/스크립트가 실측 검증 없이 방치돼 있던 패키징 단계를 처음으로
end-to-end 검증하고, 발견된 인터프리터 해석 버그를 수정해 재현 가능한
릴리스 파이프라인을 확립했다. Phase 5(Packaging) 착수·완료.

| Item | Result |
|---|---|
| Build | PyInstaller 6.16.0 + Python 3.13.0, onedir 176MB, ~50s |
| Worker smoke | `--render-worker` frozen 경로 success, 65ms 렌더 |
| GUI smoke | 8초 생존, ko 번역 로드, config/log 정상 (에러 0) |
| Release | zip + SHA256 manifest 산출 (`release_windows.ps1`) |
| Regression | 322 tests pass (앱 코드 무변경) |

## 2. What Was Found (실측 결과)

발판이 예상보다 잘 갖춰져 있었다 — 전부 **이미 존재하되 미검증** 상태:

- `pdf_control.spec`: onedir(워커 재스폰 오버헤드 회피 의도 명시), i18n
  `datas`, hidden imports, 대형 라이브러리 excludes 완비.
- `app/path_helper.py`: frozen/dev 분기(`_MEIPASS`, appdata) 완비.
- `app/viewer.py:133-135`: frozen이면 `sys.executable --render-worker`,
  dev면 `main.py --render-worker` 분기 완비.
- `main.py`: `--render-worker` 서브커맨드 엔트리 완비.
- `scripts/build_windows.ps1`·`smoke_frozen.ps1`·`release_windows.ps1`:
  파이프라인 완비.
- `app/config.py`의 루트 `config.json` 참조는 레거시 마이그레이션 전용이라
  frozen 미번들이어도 안전(기본값 폴백).

## 3. Defect Found & Fixed

**빌드 스크립트가 잘못된 Python을 사용할 수 있었다.**
`build_windows.ps1`/`smoke_frozen.ps1`이 `Get-Command python`을 썼는데,
이 머신에서 `python`은 무관한 3.11 agent venv로 해석된다(CLAUDE.md의 기존
주의사항과 동일 함정). PyInstaller가 그 venv의 site-packages로 빌드하면
조용히 잘못된(혹은 실패하는) 산출물이 나온다.

수정: `scripts/resolve_python.ps1` 신설 —
`PDF_CONTROL_PYTHON` 환경 override → `py -3.13` → bare `python`(경고와 함께
최후 폴백) 순 해석, 두 스크립트가 dot-source로 공유(DRY).

## 4. Deliverables

| Deliverable | Location | Status |
|---|---|:---:|
| Python resolver | `scripts/resolve_python.ps1` (신규) | Complete |
| Script fixes | `scripts/build_windows.ps1`, `scripts/smoke_frozen.ps1` | Complete |
| Build deps pin | `requirements-build.txt` (`pyinstaller==6.16.0`) | Complete |
| Verified artifact | `dist/PDF_Control_windows_20260720_183217.zip` (untracked) | Complete |

## 5. Verification Evidence

- 수동 스모크(스크립트 수정 전 baseline): 워커 job 직접 실행 →
  `{"success": true, "duration_ms": 66.8}` + preview.png 생성; GUI offscreen
  6초 생존 + 격리 appdata에 config/log 생성, 로그에 에러 0.
- 공식 파이프라인(수정 후): `release_windows.ps1` 1회 실행으로
  clean build → 워커 65ms success → GUI 8초 생존 → zip+SHA256 manifest.

## 6. Deferred / Follow-ups

- **CI 빌드 잡**: windows-latest에서 빌드+스모크(~2분) 자동화. 릴리스
  빈도가 생기면 추가(현재는 로컬 스크립트로 충분).
- **코드 서명 / 아이콘**: 미서명 exe는 SmartScreen 경고 발생. 배포 대상이
  생기면 처리.
- **UPX**: spec에 `upx=True`지만 UPX 미설치 시 조용히 스킵됨(현재 스킵).
  176MB 축소가 필요해지면 설치.
- 실사용자 배포 후 프리뷰 체감/스타트업 시간 피드백 수집.
