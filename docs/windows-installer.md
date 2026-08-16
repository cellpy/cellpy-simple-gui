# The Windows installer

A per-user install: no admin prompt, no UAC, nothing written outside your own
profile. A researcher on a managed laptop can install it without asking IT,
which is most of the reason for shipping an installer at all.

---

## What you will see first: a SmartScreen warning

The installer is **not code-signed**, so Windows will stop it the first time:

> **Windows protected your PC**
> Microsoft Defender SmartScreen prevented an unrecognised app from starting.
> Running this app might put your PC at risk.

To continue: **More info** → **Run anyway**.

This is not a bug and there is no trick that avoids it. SmartScreen judges an
executable by its signing certificate and by how many people have already run
it. An unsigned binary has neither, so every new release starts from zero.

**The fix is a code-signing certificate**, which is a purchase, not a code
change:

| | cost | effect |
|---|---|---|
| No certificate | — | SmartScreen warns on every release. Today's state. |
| OV certificate | ~$200–400/year | Warning persists until reputation accumulates, then fades. |
| EV certificate | ~$300–600/year + hardware token | Immediate SmartScreen reputation. |

Signing is a per-release build step (`signtool`) once a certificate exists.
Until someone decides to buy one, the honest answer to "why does Windows say
this is dangerous?" is: *because we have not paid to tell it otherwise.*

If you are distributing this internally, checking the SHA-256 of the download
against the release page is a more meaningful check than SmartScreen anyway.

---

## Installing

Run `cellpy-simple-gui-<version>-setup.exe` and click through. It installs to:

```
%LOCALAPPDATA%\Programs\cellpy-simple-gui
```

and adds a Start-menu folder with three entries: the app, a **console** variant,
and the uninstaller.

Silent install, for deploying to several machines:

```bat
cellpy-simple-gui-0.1.0-setup.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
```

### WebView2

The native window is a WebView2 host. Windows 10 and 11 ship the runtime, but
LTSC and Server images often do not — and without it the app would open a blank
window, which looks like a crash with no cause. The installer checks, and
fetches Microsoft's evergreen bootstrapper (~2 MB) if it is missing.

If that download fails the install still succeeds: without WebView2 the app
falls back to opening in your default browser, which works fine. A machine with
no internet access gets a usable install rather than a refused one.

---

## When something goes wrong

There are two executables in the install folder, and the second one exists
precisely for this:

| | |
|---|---|
| `cellpy-simple-gui.exe` | The app. No console window. |
| `cellpy-simple-gui-console.exe` | The same app with a console attached. |

A windowed program that fails during startup has nowhere to print, so it would
otherwise just… not appear. That is not hypothetical — the packaging spike
(#117) found a bundle that died at import with `ModuleNotFoundError`, and the
only reason it was diagnosable was a console. So:

- Startup failures write **`%LOCALAPPDATA%\cellpy-simple-gui\logs\startup-error.log`**
  and show a dialog naming that file.
- Normal running logs to **`%LOCALAPPDATA%\cellpy-simple-gui\logs\app.log`**
  (rotated at 2 MB, three kept).
- **Start menu → cellpy simple GUI (console)** runs the same app with the error
  on screen. That is the one to attach to a bug report.

---

## Arbin `.res` needs a Microsoft ODBC driver

**The installer does not include it, and a stock Windows machine does not have
it.** Arbin `.res` files are an Access database, and cellpy reads them on Windows
through the Access ODBC driver. Without it, importing a `.res` file fails with:

```
(pyodbc.InterfaceError) ('IM002', '[Microsoft][ODBC Driver Manager]
 Data source name not found and no default driver specified')
```

If you have Microsoft Office installed, you almost certainly already have the
driver and will never see this. That is exactly why it went unnoticed for so
long — every machine this was developed on had Office. It was a CI runner, with
a clean Windows image, that showed the truth.

**The fix** is Microsoft's free
[Access Database Engine redistributable](https://www.microsoft.com/en-us/download/details.aspx?id=54920).
Install the **64-bit** version to match the app. If you have 32-bit Office
installed, the installer will object; the usual workaround is running it with
`/quiet` from a command prompt.

Every other format is unaffected — Maccor, Neware, PEC, Bio-Logic and the
Arbin SQL/CSV/Excel exports all work with no extra driver.

## Static figure export needs Chrome

**Export ▾ → Figure** (PNG/SVG/PDF) is rendered server-side by kaleido, which
does **not** bundle a renderer — it drives a separate Chrome or Chromium.

- Chrome installed → works. Verified on the frozen build: a 168 KB PNG.
- No Chrome → a `503` saying so. Microsoft Edge is *not* a usable substitute
  here: pointed at `msedge.exe` deliberately, the render hung indefinitely
  rather than failing.

Nothing else is affected. CSV, Excel, Parquet and JSON export all work, and the
chart toolbar's camera button saves a PNG in the browser without any of this.

---

## Uninstalling

Start menu → **Uninstall cellpy simple GUI**, or Settings → Apps.

**Your data is not touched.** Projects live in `%USERPROFILE%\.cellpy_simple_gui`
and stay there; so does anything under `%USERPROFILE%\cellpy_data`. The
uninstaller removes the install folder and the app's own logs, and nothing else.

The install folder is removed *entirely*, not just the files the installer laid
down — because the app can write inside it at runtime, and earlier builds did.
Several of cellpy's directory settings default to **relative** paths, which it
resolves against the working directory; started from a Start-menu shortcut, that
is the install folder. One build downloaded ~9 MB of demo data into
`_internal\cellpy\utils\data`; the next left `cellpy_debug.log` and friends in
the root. The app now gives cellpy absolute, per-user directories for both, but
the belt-and-braces removal stays.

---

## Building it yourself

```powershell
pwsh packaging/build_installer.ps1
```

That runs PyInstaller, smoke-tests the console build, and compiles the Inno
Setup script. The smoke test is not decoration: a bundle can build cleanly and
still fail to discover cellpy's instrument loaders, and wrapping an untested
bundle in an installer only moves the discovery to a user.

Needs [Inno Setup 6](https://jrsoftware.org/isinfo.php)
(`winget install JRSoftware.InnoSetup`).

| | |
|---|---|
| Bundle | **576 MB**, 3958 files |
| Installer | **178 MB** |
| Startup, warm | ~6 s |
| Startup, very first run | ~40 s |

The first-run cost is a one-time price for touching ~4000 new files — on
Windows, largely Defender scanning them. It is long enough that the app looks
hung, which is worth a progress cue.
