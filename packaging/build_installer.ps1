<#
.SYNOPSIS
    Build the frozen app and wrap it in a Windows installer (#122).

.DESCRIPTION
    Runs PyInstaller, smoke-tests the *console* build (the windowed one has no
    stdout to read a token from), then compiles the Inno Setup script.

    The smoke test is not optional decoration: a bundle can build cleanly and
    still fail to discover cellpy's instrument loaders, which is the exact
    failure #117 exists to catch. Shipping an installer around an untested
    bundle just moves the discovery to a user.

.EXAMPLE
    pwsh packaging/build_installer.ps1
    pwsh packaging/build_installer.ps1 -Version 0.2.0 -SkipSmokeTest
#>
[CmdletBinding()]
param(
    [string]$Version = "",
    [switch]$SkipBuild,
    [switch]$SkipSmokeTest
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Push-Location $Root
try {
    if (-not $Version) {
        $pyproject = Get-Content "pyproject.toml" -Raw
        if ($pyproject -match '(?m)^version\s*=\s*"([^"]+)"') {
            $Version = $Matches[1]
        } else {
            throw "Could not read version from pyproject.toml; pass -Version."
        }
    }
    Write-Host "Building $Version" -ForegroundColor Cyan

    if (-not $SkipBuild) {
        Write-Host "==> PyInstaller" -ForegroundColor Cyan
        # --extra desktop is not optional: pywebview moved to an extra in #118,
        # and PyInstaller can only bundle what is installed. Without it you get
        # a working app that silently only ever opens a browser.
        uv run --extra build --extra desktop --extra export `
            pyinstaller packaging/cellpy-simple-gui.spec --noconfirm
        if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }
    }

    $bundle = Join-Path $Root "dist\cellpy-simple-gui"
    if (-not (Test-Path (Join-Path $bundle "cellpy-simple-gui.exe"))) {
        throw "No bundle at $bundle — run without -SkipBuild."
    }

    if (-not $SkipSmokeTest) {
        Write-Host "==> Smoke test (console build)" -ForegroundColor Cyan
        uv run python packaging/smoke_test.py (Join-Path $bundle "cellpy-simple-gui-console.exe")
        if ($LASTEXITCODE -ne 0) { throw "Smoke test failed — not packaging this." }
    }

    $iscc = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $iscc) {
        throw "Inno Setup 6 not found. Install it: winget install JRSoftware.InnoSetup"
    }

    Write-Host "==> Inno Setup" -ForegroundColor Cyan
    & $iscc "/DAppVersion=$Version" "packaging\installer.iss"
    if ($LASTEXITCODE -ne 0) { throw "ISCC failed." }

    $setup = Get-ChildItem "dist\installer\*.exe" | Sort-Object LastWriteTime | Select-Object -Last 1
    Write-Host ""
    Write-Host ("Installer: {0} ({1:N0} MB)" -f $setup.FullName, ($setup.Length / 1MB)) -ForegroundColor Green
    Write-Host "Unsigned — see docs/windows-installer.md for what SmartScreen will show users." -ForegroundColor Yellow
}
finally {
    Pop-Location
}
