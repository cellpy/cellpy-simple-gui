; Inno Setup script for cellpy simple GUI (#122)
;
; Per-user install by design: no admin prompt, no UAC, nothing written outside
; the user's profile. A researcher on a managed laptop can install this without
; asking IT, which is most of the point of shipping an installer at all.
;
; Build (from the repo root):
;   uv run pyinstaller packaging/cellpy-simple-gui.spec --noconfirm
;   & "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\installer.iss
;
; or just: pwsh packaging/build_installer.ps1

#define AppName "cellpy simple GUI"
#define AppPublisher "cellpy"
#define AppURL "https://github.com/cellpy/cellpy-simple-gui"
#define AppExe "cellpy-simple-gui.exe"
#define ConsoleExe "cellpy-simple-gui-console.exe"

; Overridable: ISCC /DAppVersion=1.2.3
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

#define SourceDir "..\dist\cellpy-simple-gui"

[Setup]
; Never change AppId — it is what lets an upgrade replace an existing install
; rather than sitting beside it, and what the uninstaller is registered under.
AppId={{F1D4A423-3214-4BAC-8334-5BF196578FCD}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
AppUpdatesURL={#AppURL}/releases
VersionInfoVersion={#AppVersion}

; lowest = never ask for admin. Combined with the {localappdata} target below
; this is the same shape as VS Code's per-user install.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=

DefaultDirName={localappdata}\Programs\cellpy-simple-gui
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
AllowNoIcons=yes
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExe}

OutputDir=..\dist\installer
OutputBaseFilename=cellpy-simple-gui-{#AppVersion}-setup
SetupIconFile=..\src\cellpy_simple_gui\web\static\img\cellpy-icon.ico
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes

; The bundle is x64 (PyInstaller froze a 64-bit Python).
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; ~576 MB unpacked; tell the wizard so the disk-space figure is not nonsense.
ExtraDiskSpaceRequired=0
LicenseFile=..\LICENSE

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
; The console build is the documented way to see a startup error, so it needs to
; be findable without a file-manager expedition.
Name: "{group}\{#AppName} (console)"; Filename: "{app}\{#ConsoleExe}"; Comment: "Run with a console window to see errors"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Logs are ours, so they go. The user's projects live in %USERPROFILE%\.cellpy_simple_gui
; and are deliberately NOT touched — uninstalling an app must not delete data
; the user spent an afternoon producing.
Type: filesandordirs; Name: "{localappdata}\cellpy-simple-gui\logs"

; Inno only removes what it installed, so anything written into {app} at runtime
; survives an uninstall. That is not hypothetical: before the app started
; creating cellpy's examples directory, a first run downloaded ~9 MB of demo
; data into {app}\_internal\cellpy\utils\data and the uninstall left it there.
; That specific cause is fixed, but a per-user install directory we created is
; ours to remove entirely — belt and braces against the next such surprise.
Type: filesandordirs; Name: "{app}"

[Code]
const
  { Registered by the WebView2 evergreen runtime, machine-wide or per-user. }
  WV2_CLIENT = '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  WV2_BOOTSTRAPPER = 'https://go.microsoft.com/fwlink/p/?LinkId=2124703';

var
  DownloadPage: TDownloadWizardPage;

function WebView2Version(RootKey: Integer; const SubKey: String): String;
begin
  Result := '';
  if not RegQueryStringValue(RootKey, SubKey, 'pv', Result) then
    Result := '';
end;

function WebView2Installed(): Boolean;
var
  Version: String;
begin
  { Machine-wide (64-bit view, then native), then per-user. Any one is enough. }
  Version := WebView2Version(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\' + WV2_CLIENT);
  if Version = '' then
    Version := WebView2Version(HKLM, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\' + WV2_CLIENT);
  if Version = '' then
    Version := WebView2Version(HKCU, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\' + WV2_CLIENT);

  Result := (Version <> '') and (Version <> '0.0.0.0');
end;

function OnDownloadProgress(const Url, FileName: String; const Progress, ProgressMax: Int64): Boolean;
begin
  Result := True;
end;

procedure InitializeWizard();
begin
  DownloadPage := CreateDownloadPage(
    SetupMessage(msgWizardPreparing), SetupMessage(msgPreparingDesc), @OnDownloadProgress);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
  if (CurPageID <> wpReady) or WebView2Installed() then
    Exit;

  { The native window is a WebView2 host. Windows 10/11 ship the runtime, but
    LTSC and Server images do not, and there the app would start and show a
    blank window — a failure with no obvious cause. Fetch the evergreen
    bootstrapper (~2 MB; it pulls the runtime itself).

    Not fatal if it fails: without WebView2 the app falls back to opening in the
    default browser, which works fine. So a machine with no network still gets
    a usable install rather than a refused one. }
  DownloadPage.Clear;
  DownloadPage.Add(WV2_BOOTSTRAPPER, 'MicrosoftEdgeWebview2Setup.exe', '');
  DownloadPage.Show;
  try
    try
      DownloadPage.Download;
      Exec(ExpandConstant('{tmp}\MicrosoftEdgeWebview2Setup.exe'),
           '/silent /install', '', SW_SHOW, ewWaitUntilTerminated, ResultCode);
    except
      { {#AppName} is a preprocessor define, so it has to be substituted into a
        string literal here — it is not a Pascal identifier. }
      SuppressibleMsgBox(
        'The WebView2 runtime could not be installed.' + #13#10#13#10 +
        '{#AppName} will still work — it opens in your default browser instead ' +
        'of a native window.',
        mbInformation, MB_OK, IDOK);
    end;
  finally
    DownloadPage.Hide;
  end;
end;
