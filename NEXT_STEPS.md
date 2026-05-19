# Next Steps (2025-12-16)

> **⚠️ DEPRECATED**: This document has been migrated to the new **bkit PDCA** structure.
>
> **See**: [`docs/01-plan/features/next-steps.plan.md`](docs/01-plan/features/next-steps.plan.md) for current action items.
>
> **Quick Links**:
>
> - [Documentation Index](docs/_INDEX.md)
> - [Improvement Roadmap](docs/01-plan/features/improvement.plan.md)
> - [README](README.md)

---

## 상태 요약

- 텍스트 교체: 좌측 정렬, 우/하단 확장(14/12pt), 폭 기반 폰트 크기(이진 탐색) 적용. 4~5글자 안정, 매우 긴 텍스트는 여전히 축소/실패 로그 가능.
- UX: 상태바 페이지/줌 표시, 렌더 진행 메시지, 로그 경로 복사, 히스토리 토글/시각화, 기본 스타일 적용.
- 안정성: config 깊은 복사, temp_doc 정리, RemoveSection 메모리 가드, 테스트 픽스처 정리.

## 우선 개선 항목

1. 긴 텍스트 대응
   - 선택적 “폰트 크기 고정” 옵션 추가(Replace/Batch), 기본 8~10pt 범위 제안.
   - 축소/실패 시 상태바 안내(“영역이 좁아 자동 축소/실패, 영역을 넓히거나 작은 크기를 선택하세요”).
   - (필요 시) 확장 폭 소폭 추가 또는 줄바꿈 허용 정책 명시.
2. 프리뷰-저장 로직 완전 단일화
   - `DocumentSession.apply_operations_to_page`를 재사용 가능한 함수/서비스로 분리, RenderWorker가 동일 코드 경로 사용.
   - 폭 기반 크기 계산/패딩/정렬 파라미터를 공용 설정으로 관리.
3. UI/UX 다듬기
   - 선택 없이 작업 시 토스트/안내 고도화.
   - 히스토리 항목에 더 많은 메타(시간, 폰트, 축소 여부) 표시.
   - Remove/Crop 다이얼로그에 예상 높이/파일 크기 변화 안내.
   - 축소 발생 시 시각적 표시(상태바/히스토리 라벨).
4. 테스트/품질
   - 프리뷰=저장 동등성 테스트 추가(텍스트 존재/해시 비교).
   - i18n 키/플레이스홀더 검증 스크립트 CI 적용.
   - 긴 텍스트/좁은 영역/줄바꿈 케이스 UI 테스트 추가.
5. 기능 확장 아이디어
   - 스팬/라인 오버레이 선택 UI(웹 에디터 느낌)로 정밀 선택 지원.
   - 교체 템플릿/즐겨찾기(자주 쓰는 문구/폰트) 기능.
   - 작업 요약/로그 내보내기(페이지별 작업, 시간, 폰트).
6. 배포/문서
   - PyInstaller spec 정리, 경로 헬퍼/데이터 동봉 검증.
   - README/CHANGELOG에 최근 변경(텍스트 교체 개선, UX 업데이트) 기록.
