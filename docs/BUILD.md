# Building PDF Control

Windows packaging is validated with `PyInstaller` in `onedir` mode.

`onedir` is intentional. The viewer now renders previews through a separate worker process (`--render-worker`), and repeatedly launching a `onefile` binary would add avoidable unpack/startup cost to every preview render.

## Prerequisites

```powershell
pip install -r requirements-build.txt
```

## Build

```powershell
.\scripts\build_windows.ps1
```

Equivalent direct command:

```powershell
pyinstaller --clean --noconfirm pdf_control.spec
```

Build output:

```text
dist/
  PDF_Control/
    PDF_Control.exe
    ...
```

## Optional ZIP

```powershell
.\scripts\build_windows.ps1 -Zip
```

This produces `dist/PDF_Control_windows.zip`.

## Automated Smoke Test

```powershell
.\scripts\smoke_frozen.ps1
```

This runs the frozen render worker and then launches the frozen GUI briefly to verify startup stability.

## Validation

1. Run `dist\PDF_Control\PDF_Control.exe`.
2. Open a sample PDF and verify open/save, delete/replace, crop, remove-section, undo/redo.
3. Change zoom several times and confirm previews remain responsive.
4. Confirm logs are written under `%APPDATA%\PDF_Control\logs` in a frozen build.
5. Confirm `en/ko` switching still loads bundled translations.

For a one-command release flow:

```powershell
.\scripts\release_windows.ps1
```

## Worker Smoke Test

The frozen app includes the preview worker entrypoint in the same executable:

```powershell
$p = Start-Process -FilePath .\dist\PDF_Control\PDF_Control.exe `
    -ArgumentList '--render-worker', '<job.json>' `
    -PassThru -Wait
$p.ExitCode
```

This is useful for diagnosing packaging issues without launching the full GUI.

## Troubleshooting

`Missing translations`
Check that `app/i18n/*.json` is present in `datas` inside [pdf_control.spec](/C:/X/Tools/PDF_Control/pdf_control.spec).

`Preview render works in dev but not in frozen build`
Verify [app/render_worker.py](/C:/X/Tools/PDF_Control/app/render_worker.py) and [app/pdf_engine.py](/C:/X/Tools/PDF_Control/app/pdf_engine.py) remain included in `hiddenimports`.

`Executable starts but Defender warns`
Unsigned Windows binaries often trigger reputation checks. For external distribution, code signing is the next step after build validation.
