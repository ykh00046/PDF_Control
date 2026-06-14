# Pyproject + Ruff - Design

> **Summary**: pyproject.toml 구성(ruff/pytest/mypy) + mypy.ini 1:1 변환 매핑 + ruff 위반 정리 절차
>
> **Author**: Claude (bkit)
> **Created**: 2026-06-14
> **Status**: ✅ Completed (2026-06-15, 매치율 100%)
> **Plan**: [pyproject-ruff.plan.md](../../01-plan/features/pyproject-ruff.plan.md)

---

## 1. pyproject.toml

```toml
[project]
name = "pdf-control"
version = "0.1.0"
requires-python = ">=3.13"
# Dependencies stay in requirements.txt (CI uses pip install -r); see plan Won't.

[tool.ruff]
line-length = 120
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "I", "W"]

[tool.ruff.lint.per-file-ignores]
# Scratch scripts bootstrap sys.path before importing app (intentional E402).
"scripts/*" = ["E402"]

[tool.pytest.ini_options]
testpaths = ["tests"]
norecursedirs = ["logs", ".appdata", ".pytest_cache"]

[tool.mypy]
python_version = "3.13"
ignore_missing_imports = true
follow_imports = "silent"
warn_unused_ignores = true

# operations package: strict, with the two relaxations from mypy.ini.
[[tool.mypy.overrides]]
module = ["app.operations.*"]
strict = true
disallow_any_decorated = false
warn_return_any = false

# Backward-compat shim -- re-export only.
[[tool.mypy.overrides]]
module = ["app.operations_service"]
ignore_errors = true

# Clean leaf modules + model facade: plain strict.
[[tool.mypy.overrides]]
module = [
    "app.config", "app.logger", "app.path_helper", "app.text_utils",
    "app.text_metadata", "app.fonts", "app.page_split", "app.encryption",
    "app.model",
]
strict = true

# Legacy-core: strict but fitz-facing Any returns allowed (no stubs).
[[tool.mypy.overrides]]
module = ["app.document_model", "app.pdf_engine", "app.document_session"]
strict = true
warn_return_any = false
```

매핑 검증 (mypy.ini → pyproject, 1:1):

| mypy.ini 블록 | pyproject override | strict |
|---|---|---|
| `[mypy]` 전역 | `[tool.mypy]` | — |
| `[mypy-app.operations.*]` (+disallow_any_decorated=F, warn_return_any=F) | overrides #1 | ✅ |
| `[mypy-app.operations_service]` ignore_errors | overrides #2 | ignore |
| leaf 8 (config..encryption) + model | overrides #3 | ✅ |
| document_model/pdf_engine/document_session (+warn_return_any=F) | overrides #4 | ✅ |

- `model`은 mypy.ini에서 strict only(warn_return_any 명시 없음) → overrides #3(plain strict)에 배치. 정확.

## 2. ruff 위반 정리 (M2)

1. `ruff check app tests scripts main.py --fix` — W293/W291/W292/I001/F401/F541 자동수정(176).
2. 수동:
   - **E712**(5, batch_replace_dialog/viewer/tests): `== True`→직접/`is True`, `== False`→`not`/`is False`. 동작 보존.
   - **F841**(4): 미사용 변수 삭제 또는 `_` 명명.
   - **E701**(3): `if x: stmt` → 두 줄 분리.
   - **E501**(9 @120): 줄바꿈 또는 불가피한 경우 `# noqa: E501`.
3. `ruff check ...` 0 위반 확인.

## 3. mypy strict 적용 스모크 (M4 검증 — plan §3)

```
1. applicator.py에 임시 삽입: def _ruff_smoke(x): return x   # untyped
2. mypy -p app.operations  → error: Function is missing a type annotation
3. 삭제. strict 살아있음 확정.
```

## 4. CI (M5)

`.github/workflows/ci.yml`의 pytest 단계 앞에:
```yaml
      - run: ruff check app tests scripts main.py
```

## 5. 검증 절차

1. pyproject 작성 → `mypy -p app.operations` + leaf 모듈 mypy 0 에러(이전 동작 보존).
2. strict 적용 스모크(§3).
3. ruff --fix + 수동 → `ruff check` 0.
4. pytest.ini/mypy.ini 삭제 → 전체 스위트(294+) + test_mypy.
5. gap-detector(1:1 매핑 대조) → CI green.
