# Enterprise Packaging and Release Guide (PySide6)

This guide describes how to package this PySide6 desktop app with `pyside6-deploy`, build a Windows installer, prepare code-signing, and publish release artifacts in an enterprise-friendly layout.

## 1) Prerequisites and baseline assumptions

- Repository packaging metadata already exists in `pyproject.toml` and targets Python 3.11+.
- App entrypoint is `python -m app.main`.
- CI runners should use a clean Windows VM image for reproducible packaging.

Reference snippets from this project:

- Project metadata and dependencies (`PySide6`, `setuptools`, etc.): `pyproject.toml`.
- Startup entrypoint: `src/app/main.py`.

## 2) Package with `pyside6-deploy`

`pyside6-deploy` is the official Qt for Python deployment helper. In practice it wraps bundle analysis and freezing steps for your target platform.

### 2.1 Create a dedicated packaging environment

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
pip install pyside6-deploy nuitka
```

> Why: separate packaging dependencies from dev dependencies and keep lockstep reproducibility in CI.

### 2.2 Initialize deployment config

```powershell
pyside6-deploy --init
```

This generates a deployment spec file (for example `pysidedeploy.spec`). Commit it so release builds are deterministic.

### 2.3 Configure the deploy spec

Set these key values in your spec:

- **Input script**: `src/app/main.py` (or a thin wrapper script if needed).
- **Project directory**: repository root.
- **Output directory**: `dist/app/`.
- **Executable name**: stable product name, e.g. `DesktopApp.exe`.
- **Include data**: config templates, migrations, static assets.
- **Plugin inclusion**: ensure Qt platform plugin (`qwindows`) and image formats are included.

If you use environment files (`.env`), do **not** package production secrets. Ship a template only.

### 2.4 Build the distributable app

```powershell
pyside6-deploy --config-file pysidedeploy.spec --force
```

Expected result: a self-contained application directory under `dist/app/` containing `DesktopApp.exe`, required Qt DLLs, plugins, and bundled Python runtime.

### 2.5 Validate the package

On a fresh Windows VM:

1. Copy only the packaged output (not source tree).
2. Launch the executable.
3. Smoke-test startup path (settings load, logging setup, DB init, Liquibase checkpoint).
4. Confirm no missing DLL/plugin errors.

## 3) Generate a Windows installer

For enterprise desktop rollout, use a signed installer format that IT teams can distribute via Intune/SCCM/GPO.

Common options:

- **MSI** (best for enterprise deployment tooling).
- **EXE bootstrapper** (Inno Setup/NSIS) for richer UX.
- **MSIX** if your organization has Store-style deployment standards.

### 3.1 Example with Inno Setup (EXE)

Create `installer/desktop-app.iss`:

```ini
[Setup]
AppName=Desktop App
AppVersion=0.1.0
DefaultDirName={autopf}\Desktop App
DefaultGroupName=Desktop App
OutputDir=dist\installer
OutputBaseFilename=DesktopApp-Setup-0.1.0
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64

[Files]
Source: "dist\app\*"; DestDir: "{app}"; Flags: recursesubdirs

[Icons]
Name: "{group}\Desktop App"; Filename: "{app}\DesktopApp.exe"
Name: "{commondesktop}\Desktop App"; Filename: "{app}\DesktopApp.exe"

[Run]
Filename: "{app}\DesktopApp.exe"; Description: "Launch Desktop App"; Flags: nowait postinstall skipifsilent
```

Build command:

```powershell
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\desktop-app.iss
```

Output: `dist/installer/DesktopApp-Setup-0.1.0.exe`.

### 3.2 MSI alternative

If your enterprise mandates MSI:

- Generate app image with `pyside6-deploy` first.
- Use WiX Toolset to author MSI around `dist/app` payload.
- Include upgrade code/product code strategy and silent install flags (`/qn`).

## 4) Code-signing plan (application + installer)

Enterprise environments usually require signed binaries to avoid SmartScreen warnings and satisfy endpoint policies.

## 4.1 What to sign

Sign in this order:

1. Main executable (`DesktopApp.exe`).
2. Critical DLLs if policy requires per-binary signing.
3. Final installer (`.exe` or `.msi`).

### 4.2 Recommended signing architecture

- Store signing cert in HSM/cloud key vault (Azure Key Vault, DigiCert KeyLocker, etc.).
- Use short-lived access tokens in CI (OIDC/service principal), not exported private keys.
- Enforce timestamping so signatures remain valid after cert expiry.

### 4.3 `signtool` examples

```powershell
# Sign app executable
signtool sign /fd SHA256 /td SHA256 /tr http://timestamp.digicert.com /n "Your Company, Inc." dist\app\DesktopApp.exe

# Sign installer
signtool sign /fd SHA256 /td SHA256 /tr http://timestamp.digicert.com /n "Your Company, Inc." dist\installer\DesktopApp-Setup-0.1.0.exe

# Verify signatures
signtool verify /pa /v dist\app\DesktopApp.exe
signtool verify /pa /v dist\installer\DesktopApp-Setup-0.1.0.exe
```

### 4.4 Operational controls

- Restrict signing to release branches/tags.
- Require approval for production signing jobs.
- Emit immutable audit logs for every signing event.
- Rotate certs before expiry and test renewed cert in pre-prod.

## 5) Release artifact organization for enterprise distribution

Use a predictable release structure so desktop engineering and security teams can validate and mirror artifacts.

Suggested directory layout:

```text
releases/
  0.1.0/
    checksums/
      SHA256SUMS.txt
      SHA256SUMS.sig
    sbom/
      sbom.spdx.json
    windows/
      app-image/
        DesktopApp.exe
        ...
      installer/
        DesktopApp-Setup-0.1.0.exe
      symbols/
        DesktopApp.pdb
    docs/
      release-notes.md
      deployment-guide.md
      support-matrix.md
```

### 5.1 Publish these minimum artifacts

- Signed installer.
- Detached checksum manifest (SHA-256).
- SBOM (SPDX or CycloneDX).
- Release notes (features, fixes, known issues, rollback instructions).
- Signature verification instructions for IT admins.

### 5.2 Naming conventions

Use consistent, machine-parseable names:

- `DesktopApp-<version>-win-x64-setup.exe`
- `DesktopApp-<version>-win-x64-portable.zip` (optional)
- `DesktopApp-<version>-sbom.spdx.json`

### 5.3 Provenance and retention

- Attach build metadata: git commit SHA, build ID, CI workflow URL.
- Keep at least: current, previous, and LTS release channels.
- Store artifacts in immutable object storage with lifecycle policies.

## 6) Recommended CI/CD release flow

1. Run tests/lint.
2. Build app with `pyside6-deploy` on Windows.
3. Create installer (Inno/WiX).
4. Sign binaries and installer.
5. Verify signatures and checksums.
6. Generate SBOM.
7. Publish artifacts to release bucket and internal package portal.
8. Trigger staged rollout (pilot ring -> broad ring).

## 7) Project-specific notes for this repository

- Keep the runtime invocation aligned with `src/app/main.py`.
- Ensure deployment includes any files needed by Liquibase startup paths and config loading.
- Keep version values synchronized between `pyproject.toml`, installer metadata, and release artifact names.

