# Packaging Hardening Plan

> **Status**: Complete
> **Project**: PDF Control
> **Date**: 2026-07-20
> **PDCA Cycle**: packaging-hardening

## 1. Background

pyinstaller-packaging 사이클이 보류한 3건(CI 빌드 잡, 코드 서명, UPX)을
폐쇄한다. 목표는 "패키징이 조용히 깨지지 않는 상태"와 "서명 준비된
파이프라인"이며, 각 항목은 실측 근거로 do/won't-do를 판정한다.

## 2. Requirements

| # | Requirement | 판정 |
|---|---|---|
| R1 | CI에서 빌드+frozen 스모크가 게이트로 돌고 배포 zip이 아티팩트로 남는다 | Do |
| R2 | 인증서가 주어지면 릴리스 스크립트가 exe를 서명한다(미제공 시 기존 동작 불변) | Do (서명 준비만 — 인증서 확보는 사용자/조직 결정) |
| R3 | UPX 적용 여부를 실측 근거로 확정한다 | **Won't-do로 확정** |

## 3. Success Criteria

- main push CI에서 test·build 두 잡 모두 green, 아티팩트 업로드 확인
- 비서명 로컬 릴리스 파이프라인 무회귀(zip+SHA256+manifest)
- manifest에 signed 여부 기록
- UPX 결정이 spec에 주석으로 기록됨

## 4. Decisions (사전 판정 근거)

- **UPX won't-do**: Qt/PySide6 DLL 압축은 로더 크래시·백신 오탐의 알려진
  원인이고, 전달 형태가 zip(177MB→77MB)이라 크기 이득이 위험을 정당화하지
  못한다. 미서명 사내 배포에서 오탐 리스크는 특히 치명적.
- **서명은 "준비"까지만**: 자가서명은 SmartScreen을 해소하지 못하고(신뢰
  배포된 머신에서만 유효), 실질 해소는 구매 OV/EV 인증서 + 평판 축적 —
  비용 결정이라 파이프라인만 서명-가능 상태로 만든다.
- **CI 빌드는 main push 한정**: PR은 test 잡으로 충분, 77MB 아티팩트/빌드
  시간을 PR마다 지출하지 않는다.
