# Tools

도구 프로젝트 모음. **2026-07-23 대청소** 이후 활성 항목은 PDF_Control 하나다.

## 프로젝트 구조
- `PDF_Control/`: PDF 제어/조작 도구 (Python, **활성** — GitHub CI, `_ops/projects.json` 관제 등재됨)
- `json/`: `flow_idea.json`(아이디어 메모)만 잔류 — 시크릿 파일들은 `C:\Users\interojo\.secrets\`로 이동 (`json/MOVED.md` 참조)

## 2026-07-23 정리 이력 (없어진 것들)
- `n8n-main/` **삭제** — 커밋 0·원격 0의 순정 소스 덤프(의존성 파손, 3월 이후 방치). 필요 시 `git clone https://github.com/n8n-io/n8n` 재확보
- `Program-estimation/` → `C:\X\_archive\` (IRMS로 통합 완료, 태그 archived-202607)
- `WebAutomation/` → `C:\X\_archive\WebAutomation-leave-request\` (휴가신청 자동화 — 루트에 있던 동명의 워크플로 러너와 별개)
- 루트 `skills serching api.txt` → `.secrets`로 이동, `docs/`(bkit 상태 파일만 있던 폴더) 삭제

## Recent Context
- R1 bkit 개선 완료
- R2 개선 완료 (2026-06-02, r2-quality-fixes PDCA): get_text_length API 버그 수정(11 테스트 복구) + mypy strict 게이트 6개 모듈 확대 + Preview/Save DRY 회귀검증. 결과 128 passed.
- text-wrap-replace 완료 (2026-06-02, PDCA): 긴 텍스트 교체 시 폰트 축소 대신 자동 줄바꿈(멀티라인 워드랩)으로 박스 높이를 페이지 경계 내 확장. wrap-first→shrink 폴백 정책. `text.wrapped`(info) 경고 신설. 결과 146 passed. 핵심: `applicator.py::_wrap_line_count`+`_insert_text_with_autofit`.
- replace-wrap-toggle 완료 (2026-06-08, PDCA): wrap-first 정책을 전역 상수→교체 단위 사용자 선택으로 노출. `RedactReplace.wrap`(None=전역/True=줄바꿈/False=축소) + BatchReplaceDialog "긴 텍스트 줄바꿈" 체크박스. 100% 하위 호환, 매치율 100%, 195 passed.
- pdf-encryption 완료 (2026-06-08, PDCA): AES-256 암호화 저장(사용자/소유자 암호 + 권한 비트). File→"Encrypt & Save As…"(Ctrl+Alt+S). `app/encryption.py`(strict) `EncryptionSettings`. 191 passed.
- pdf-open-decrypt 완료 (2026-06-08, R3 PDCA): pdf-encryption의 짝. 암호화 PDF 열기(비번 프롬프트+재시도) + 보호 해제(복호화 저장, File→Remove Protection, Ctrl+Alt+D). `open_document(path,password)` 인증+`PasswordRequired`/`IncorrectPassword`, 세션 `_password`/`is_encrypted` 단일 소유→전 재오픈 경로 스레딩. 100% 하위 호환, 매치율 100%, 208 passed.
- r4-bugfix 완료 (2026-06-10, R4 PDCA): 2026-06-10 전체검토에서 검증된 버그 3건 수정. (B1) `mypy.ini` em-dash→cp949 mypy 기동실패로 깨진 게이트 복구(ASCII-only 주석 추가), (B2) `Operation.from_dict`의 `wrap` 복원 누락으로 미리보기가 교체별 줄바꿈 선택을 무시하던 preview≠save 회귀 수정+op 4종 round-trip 테스트 신설, (B3) 렌더 워커 비번 평문 job 파일 기록을 stdin 파이프 1줄 프로토콜로 전환+`render_password()` 캡슐화. 매치율 100%, 221 passed.
- r5-infra 완료 (2026-06-10, R5 PDCA): GitHub Actions CI 신설(windows-latest, py3.13, `QT_QPA_PLATFORM=offscreen`, pytest 단일 step에 mypy 게이트/i18n/drift 가드 포함 — 첫 실행은 push 시), requirements.txt 전 항목 `==` 핀(+누락이던 mypy/pytest-timeout/PyYAML 명시), `app/ui_handlers.py` 셰임 제거, deprecated 루트 문서 3종→`docs/archive/legacy-root/`, 스크래치 스크립트 5종→`scripts/`(경로 부트스트랩). pyproject/ruff는 의도적 보류. 매치율 100%, 221 passed.
- r6-quality 완료 (2026-06-10, R6 PDCA): controller 예외 보일러플레이트 14곳→`_run_session_action` 가드 1곳(ValueError=warning/내부=error 분리, int 반환 0의 거짓 실패 방지), applicator 지연 import 6곳→상단 직수입 + `_insert_text_with_autofit` 150줄→58줄 분해(동작 불변), typing-legacy-core 해소(pdf_engine/document_session/document_model/model strict 승격, leaf 12모듈). 매치율 100%, 226 passed. **CI 첫 실행 성공**(windows-latest 1m11s).
- r7-history-policy 완료 (2026-06-11, R7 PDCA): 페이지 재배열(move/duplicate/merge/드래그 정렬) 시 히스토리 폐기→**물리 페이지 추종 리매핑** 보존으로 정책 통일(`_remap_history_after_reorder` 단일 경로, redo만 무효화). move 리매핑은 PyMuPDF `move_page` 시맨틱 실측(frm<to→to-1, frm>to→to) 기반. 신규 `reorder_pages()` public API로 page_manager 캡슐화 위반 해소. RemoveSection 가짜 진행률 제거(H3 재검증: op 추가는 즉시, 렌더는 이미 워커 비동기 — 25/50/75는 장식이었음) + i18n 6키 정리. 매치율 100%, 235 passed.
- text-fidelity 완료 (2026-06-11, PDCA): 교체 텍스트가 원본 서체·크기·베이스라인을 따라가도록 충실도 개선. `fonts.resolve_pdf_fontname`(레지스트리 매칭+글리프 커버리지) + applicator 우선순위 체인(사용자 명시>시스템 매칭>Base-14 추출메타 기준 — **배치 교체 항상 helv 버그 해소**) + `TextMetadata.baseline` 앵커링(실측 200.0→200.0 정확) + rect 크기 부풀림 제거. 매치율 100%, 254 passed.
- embedded-font-reuse 완료 (2026-06-13, PDCA): 충실도 체인 최종 단계. 미설치 원본 폰트도 PDF 임베디드 폰트(`doc.extract_font`)를 추출·재사용. `fonts.extract_embedded_font` + applicator 체인 `op.fontfile>시스템 매칭>임베디드>Base-14`. 핵심 함정: `apply_redactions`가 미참조 폰트 리소스 스트립 → 추출 전/등록 후(`_register_fonts` Pass 2.5) 분리. 서브셋 임베드는 cmap 제거로 자동 거부(안전 폴백). 별칭 crc32 충돌방지. 매치율 100%, 261 passed.
- save-integrity 완료 (2026-06-14, PDCA): **데이터 손실 버그 수정** — 페이지 관리 변경(삭제/회전/이동/재배열 등)이 저장 시 손실되던 문제(save가 원본 파일 재오픈해 history op만 적용). `save_document_copy(source_bytes=)` + 세션이 `self.doc.tobytes()`(페이지 관리 반영 평문 스냅샷) 전달로 수정. 출력 암호화/하위호환 불변. async-save 실측 중 발견. `source_bytes`는 async-save 워커 입력 구조와 동일. 매치율 100%, 268 passed.
- save-busy-indicator 완료 (2026-06-14, PDCA): async-save 측정(대부분 저장 <1s, tobytes 직렬화는 비동기화해도 메인 잔존, 풀 워커는 최고 위험) 결과 **풀 async-save 대신 경량 busy 표시** 선택. `_commit_save`에 WaitCursor+`status.saving`+processEvents, finally 복원. 저장 UI 경로 첫 테스트. 매치율 100%, 271 passed.
- watermark 완료 (2026-06-14, PDCA): 텍스트 워터마크(반투명·대각선) Tools→Add Watermark(Ctrl+Shift+W). `WatermarkText` op(`TextWriter`+morph, 비파괴 Pass 5, SAVE/PREVIEW 공유), `controller.add_watermark(page_indices,...)` 범위별 op(Qt-free), 다이얼로그, i18n 12키. 매치율 100%, 281 passed. 확장: 이미지 워터마크.
- text-export-range 완료 (2026-06-14, PDCA): 텍스트 내보내기 "페이지 범위" 끊긴 연결 수정(get_settings가 range 버려 현재 페이지만 내보내던 것 + 누락 i18n 2키 복구). `parse_page_ranges` 재사용, 백엔드 신규 0. 매치율 100%, 287 passed.
- image-watermark 완료 (2026-06-14, PDCA): 이미지 워터마크(로고) Ctrl+Shift+I. `WatermarkImage` op. PyMuPDF insert_image 제약(opacity 없음→Pixmap 알파 우회, 회전 90단위만) probe+Context7 확인. applicator Pass 5에 텍스트/이미지 공유. 매치율 100%, 294 passed.
- pyproject-ruff 완료 (2026-06-15, PDCA): pytest.ini+mypy.ini→pyproject.toml 통합, ruff 0.14.4 린터 도입(0 위반, CI 게이트). mypy strict 1:1 보존(스모크 검증 — strict 약화는 0 에러로 가려지니 untyped def 삽입 검출 확인). line-length 120. 294 passed. 설정은 이제 pyproject.toml 단일 소스(mypy.ini/pytest.ini 삭제됨).
- validate-i18n-refs 완료 (2026-06-15, PDCA): i18n 검증에 tr() 참조 키 존재 검사 추가(동수만 보던 공백). 측정 중 remove_section_dialog 5키 양쪽 누락 + 죽은 fallback 관용구(UI에 raw 키 노출) 발견·수정. 295 passed.
- ruff-format 완료 (2026-06-15, PDCA): ruff 포매터 전 코드베이스 적용(75/84 파일, 동작 불변 — 토큰 보존, 295 passed+mypy strict 0). CI에 format --check 게이트, .git-blame-ignore-revs로 blame 완화. ruff = check+format 양쪽 게이트.
- watermark-tiling 완료 (2026-06-15, PDCA): WatermarkText/Image에 tile 옵션(자동 격자 반복). 셀=max(치수)×TILE_SPACING_FACTOR, 이미지 xref 재사용, _draw_at DRY, tile=False 하위호환. 298 passed.
- page-undo-redo 완료 (2026-06-19, PDCA): 페이지 관리 undo/redo(최대 20단계, PDF bytes+pending ops 스냅샷). 변경 7종 round-trip, redo 무효화, Ctrl+Z/Ctrl+Shift+Z, 버튼 상태 동기화. 322 passed. (커밋은 2026-07-20)
- pyinstaller-packaging 완료 (2026-07-20, PDCA): Phase 5 첫 실측 — 기존 spec/스크립트 end-to-end 검증(onedir 176MB, frozen 렌더 워커 65ms, GUI 스모크 통과, `release_windows.ps1`로 zip+SHA256). 버그 수정: 빌드/스모크 스크립트가 `Get-Command python`(3.11 agent venv 오염)을 잡던 것 → `scripts/resolve_python.ps1` 공유 해석기(`PDF_CONTROL_PYTHON`→`py -3.13`→폴백). `requirements-build.txt` `pyinstaller==6.16.0` 핀. 보류: CI 빌드 잡, 코드 서명, UPX.
- packaging-hardening 완료 (2026-07-20, PDCA): 패키징 보류 3건 폐쇄 — CI build 잡(main push 빌드+frozen 스모크+zip 아티팩트), `release_windows.ps1 -SignThumbprint` 서명 준비(인증서 확보는 조직 결정), UPX won't-do 확정(Qt DLL 크래시·백신 오탐 vs zip 77MB — spec upx=False+근거).
- thumbnail-sidebar 완료 (2026-07-20, PDCA): 좌측 도크 페이지 썸네일 사이드바 — 클릭 탐색, 양방향 하이라이트 동기화, 페이지 관리 변경 갱신. fitz 스레드 비안전 → QTimer 배치 렌더+세대 가드. `app/thumbnails.py` 공유 헬퍼(DRY), `_go_to_page` 통합. 331 passed(신규 9).
- 차기 로드맵: 풀 async-save(source_bytes 발판 완비, 실측상 우선순위 낮음), 워터마크 모서리 배치/엇갈림(타일 후속), 썸네일 pending op 미리보기, ui 계층 strict 보류. 주의: `python`이 3.11 hermes venv로 잡힘 — 테스트는 Python313 절대경로로. test_async 간헐 타이밍 플레이크 1건. ruff 적용 후 git blame은 `blame.ignoreRevsFile .git-blame-ignore-revs` 권장.
