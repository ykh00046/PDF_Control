# Improvement Plan (Updated)

> **⚠️ DEPRECATED**: This document has been migrated to the new **bkit PDCA** structure.
>
> **See**: [`docs/01-plan/features/improvement.plan.md`](docs/01-plan/features/improvement.plan.md) for current improvement roadmap.
>
> **Quick Links**:
>
> - [Documentation Index](docs/_INDEX.md)
> - [Next Steps](docs/01-plan/features/next-steps.plan.md)
> - [README](README.md)

---

## 0. Objectives

- 안정성: 기본 설정 오염 방지, 렌더/저장 경로 일치, 자원 누수 제거.
- 유지보수성: 프리뷰·저장 로직 단일화, 테스트 신뢰도 확보.
- UX/I18n: 메시지·도움말 일관, 번역 무결성 자동 검증.
- 배포: PyInstaller 경로 처리/데이터 번들 체계화.

## 1. Immediate Fixes (Hotfix)

- 설정 기본값 오염 방지: `DEFAULT_CONFIG` 깊은 복사/팩토리 적용.
- 프리뷰 임시 문서 닫기: `RenderWorker.run`에서 `temp_doc.close()` 보장.
- 테스트 입력 정리: `tests/test_ui.py`의 `sample.pdf` 의존 제거(픽스처로 임시 PDF 생성).
- RemoveSection 메모리 가드: 대용량 병합 시 경고·중단 옵션 추가, DPI 상한 검토.
- 텍스트 교체 UX 개선: 좌측 정렬 유지, 우측/하단 확장, 폭 기반 폰트 크기(이진 탐색), 상세 로깅, 축소 발생 시 경고 로그.

## 2. Core Refactor

- 로직 단일화: `DocumentSession.apply_operations_to_page`를 순수 함수/서비스로 분리해 프리뷰에서도 동일 경로 사용(폰트 임베딩·텍스트박스 처리 차이 제거).
- Operation 직렬화: `Operation.from_dict/to_dict`에 검증 추가, UI↔워커 간 dict 왕복 최소화.
- 상태 주입: 로거/폰트/설정 싱글톤을 래퍼로 추상화하여 테스트 격리 가능하게.

## 3. UX & Workflow

- 상태 메시지 표준화: 열기/저장/실패/취소/선택 없음 문구 일관, 로깅 링크 제공.
- 히스토리 패널 개선: redo 스택 표기, 항목 더블클릭 시 페이지 이동(옵션).
- Remove/Crop 다이얼로그: 예상 결과(높이/파일 크기) 표시, 회전 페이지 사전 차단 메시지 명확화.
- 뷰어: 렌더 진행 상태 표시, 캐시 적중/미스 디버그 로그 옵션화.

## 4. Internationalization

- 번역 검증 스크립트: JSON 스키마 및 플레이스홀더 검사(CI에서 실행).
- 런타임 키 미스 로깅 + 기본 fallback 문자열 제공.
- 언어 전환 API 노출(메뉴/CLI 플래그) 시 캐시 무효화 포함.

## 5. Testing Strategy

- UI: `pytest-qt`로 열기/삭제/Undo/Redo/줌 비동기 렌더 흐름 검증(`qtbot.waitUntil`).
- 프리뷰=저장 동등성: 동일 연산 세트에 대해 프리뷰·저장 결과 텍스트/이미지 해시 비교 스냅샷.
- 설정: 기본값 오염 방지, 쓰기 실패 시 롤백 동작 테스트.
- RemoveSection: 빈 페이지 예외, DPI별 크기 변화, 메모리 경고 경로 테스트.
- I18n: 키 누락/중복/플레이스홀더 일치 검사.

## 6. Packaging & Deployment

- PyInstaller spec: frozen/비동결 경로 헬퍼(`get_app_dir`, `get_data_dir`), `datas`에 i18n 동봉, 테스트 모듈 제외.
- 빌드용 requirements 분리(`requirements-build.txt`), PyMuPDF/PySide6 호환 버전 명시.
- UTF-8 환경 강제(`PYTHONUTF8=1`), 윈도우 전용 여부 명시(폰트 레지스트리 의존).

## 7. Backlog & Sequencing (추천 순서)

1. Hotfix: config deepcopy, temp_doc close, 테스트 픽스처 수정, RemoveSection 메모리 가드
2. Core refactor: 프리뷰·저장 로직 공유화 + Operation 검증
3. UX 정비: 메시지/히스토리/다이얼로그/뷰어 상태 표시
4. I18n/테스트: 번역 검증 스크립트, 프리뷰=저장 동등성 테스트 추가
5. 패키징: spec 정리, 경로 헬퍼, 빌드 의존 분리, 문서화

---

문서 상태: 2025-12-16 업데이트.
