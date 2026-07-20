# Packaging Hardening Completion Report

> **Status**: Complete
> **Project**: PDF Control
> **Completion Date**: 2026-07-20
> **PDCA Cycle**: packaging-hardening

## 1. Executive Summary

pyinstaller-packaging의 보류 3건을 전부 폐쇄했다: CI 빌드 게이트 신설(Do),
릴리스 서명 단계 내장(Do — 인증서는 사용자 제공 시), UPX 명시적 폐기
(Won't-do, 근거 기록).

## 2. Deliverables

| Item | Change | Status |
|---|---|:---:|
| CI build job | `.github/workflows/ci.yml`에 `build` 잡 — main push 시 `requirements-build.txt` 설치 → `build_windows.ps1` → `smoke_frozen.ps1` → zip 아티팩트(7일 보존). `PDF_CONTROL_PYTHON`을 setup-python 인터프리터로 고정(러너 py-launcher 오해석 방지) | Complete |
| Code signing | `release_windows.ps1` `-SignThumbprint` 파라미터(또는 `PDF_CONTROL_SIGN_THUMBPRINT` env) — `Cert:\CurrentUser\My`의 인증서로 `Set-AuthenticodeSignature`(SHA256+타임스탬프). 자가서명은 체인 미신뢰 경고 후 진행, manifest에 `signed` 기록. 미제공 시 100% 기존 동작 | Complete |
| UPX decision | `pdf_control.spec` `upx=False`(EXE/COLLECT) + 폐기 근거 주석 | Complete |

## 3. Verification

- 로컬 `release_windows.ps1`(비서명) 재실행: build → worker 80ms success →
  GUI 8초 생존 → zip 77MB + SHA256 + `"signed": false` manifest.
- CI: main push에서 test·build 두 잡 green, `PDF_Control-windows` 아티팩트
  업로드 확인.

## 4. Remaining User Decision (코드 서명 실제 적용)

파이프라인은 준비 완료. 실제 SmartScreen 해소는 다음 중 하나의 **조직/비용
결정**이 필요하다:

1. **구매 인증서(OV/EV)**: 유일한 일반 배포용 해법. OV는 평판 축적 후
   경고 소멸, EV는 즉시 해소에 가깝다. 연 단위 비용 발생.
2. **자가서명 + 사내 신뢰 배포**: IT가 인증서를 사내 PC 신뢰 저장소에
   배포하면 사내 한정 유효. 비용 0, 외부 배포 불가.
3. **미서명 유지**: 현 상태. 최초 실행 시 SmartScreen "추가 정보 → 실행"
   안내 필요.

적용 시: `scripts\release_windows.ps1 -SignThumbprint <thumbprint>`.
