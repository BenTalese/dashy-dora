; Inno Setup script — wraps PyInstaller's `dist\Dora\` folder into a
; single `Dora-vX.Y.Z-windows-x64-setup.exe`.
;
; Built by `packaging\build-windows.ps1 -Installer`, which passes the
; defines below on the ISCC command line. Run by hand:
;
;   ISCC /DAppVersion=1.0.1 /DSourceDir=dist\Dora /DOutputDir=dist ^
;        /DOutputBaseFilename=Dora-v1.0.1-windows-x64-setup ^
;        /DIconFile=build\dora.ico packaging\windows\dora.iss
;
; Installs per-user by default (no admin prompt) into
; %LOCALAPPDATA%\Programs\Dora; the first page offers "install for all
; users" for people who want Program Files. User data lives in
; %LOCALAPPDATA%\BenTalese\Dora\ (platformdirs) and is NOT touched by uninstall, so
; reinstalling or upgrading keeps the household's data.

#ifndef AppVersion
  #error AppVersion must be defined (e.g. /DAppVersion=1.0.1)
#endif
#ifndef SourceDir
  #define SourceDir "..\..\dist\Dora"
#endif
#ifndef OutputDir
  #define OutputDir "..\..\dist"
#endif
#ifndef OutputBaseFilename
  #define OutputBaseFilename "Dora-v" + AppVersion + "-windows-x64-setup"
#endif

; Windows' file-version fields only take numbers, so strip any
; pre-release suffix ("1.1.0-rc.1" -> "1.1.0") for VersionInfoVersion.
#define NumericVersion Copy(AppVersion, 1, (Pos("-", AppVersion) > 0 ? Pos("-", AppVersion) - 1 : Len(AppVersion)))

[Setup]
; Fixed forever — Windows uses it to recognise upgrades of the same app.
AppId={{D142F513-DB10-4A1F-93D0-03556A778B8D}
AppName=Dashy Dora
AppVersion={#AppVersion}
AppVerName=Dashy Dora {#AppVersion}
AppPublisher=Dashy Dora
AppPublisherURL=https://github.com/BenTalese/dashy-dora
AppSupportURL=https://github.com/BenTalese/dashy-dora/issues
AppUpdatesURL=https://github.com/BenTalese/dashy-dora/releases
VersionInfoVersion={#NumericVersion}
DefaultDirName={autopf}\Dora
DefaultGroupName=Dashy Dora
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename={#OutputBaseFilename}
#ifdef IconFile
SetupIconFile={#IconFile}
#endif
UninstallDisplayIcon={app}\Dora.exe
UninstallDisplayName=Dashy Dora
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; Dora runs headless (no window), so ask Restart Manager to close a
; running copy before files are replaced or removed.
CloseApplications=force
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Dashy Dora"; Filename: "{app}\Dora.exe"
Name: "{autodesktop}\Dashy Dora"; Filename: "{app}\Dora.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Dora.exe"; Description: "{cm:LaunchProgram,Dashy Dora}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Belt and braces for the uninstaller: Restart Manager normally closes
; Dora, but a copy started from another session can slip past it.
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM Dora.exe"; Flags: runhidden; RunOnceId: "KillDora"
