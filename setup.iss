; ============================================================
;  NgweLwe — Unified Installer  (v1.0.0-beta)
;  Installs Client only, or Client + Server based on user choice.
;  Requires Inno Setup 6: https://jrsoftware.org/isdl.php
; ============================================================

#define AppName    "NgweLwe"
#define AppVersion "1.0.0-beta"
#define ClientExe  "NgweLwe.exe"
#define ServerExe  "NgweLweServer.exe"
#define AppId      "B5A3C8D2-9F1E-4A7B-8C3D-2E6F0A1B4C5D"

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=NgweLwe
AppPublisherURL=

; Per-user install — no admin rights needed
DefaultDirName={localappdata}\Programs\{#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Output
OutputDir=installer
OutputBaseFilename=NgweLwe-v{#AppVersion}-Setup
Compression=lzma2
SolidCompression=yes

; Wizard appearance
WizardStyle=modern
WizardSizePercent=100
SetupIconFile=assets\app_icon.ico

; Uninstall
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\assets\app_icon.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; \
  Description: "Create a &desktop shortcut"; \
  GroupDescription: "Additional icons:"

; ── Files ─────────────────────────────────────────────────────
; Client files are ALWAYS installed.
; Server files are installed ONLY when the user selects Host mode.
; Both dist folders share identical _internal\ (PyQt6/FastAPI DLLs),
; so installing them to the same {app} root merges cleanly.
[Files]

; Client — always
Source: "dist\NgweLwe\*"; \
  DestDir: "{app}"; \
  Flags: ignoreversion recursesubdirs createallsubdirs

; Server — Host mode only
Source: "dist\NgweLweServer\*"; \
  DestDir: "{app}"; \
  Flags: ignoreversion recursesubdirs createallsubdirs; \
  Check: IsHostInstall

; Logos — skip silently if the folder is empty or missing
Source: "dist\NgweLwe\assets\logos\*"; \
  DestDir: "{app}\assets\logos"; \
  Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist

; ── Shortcuts ─────────────────────────────────────────────────
[Icons]

; Client shortcut — always
Name: "{autoprograms}\{#AppName}"; \
  Filename: "{app}\{#ClientExe}"; \
  IconFilename: "{app}\assets\app_icon.ico"
Name: "{autodesktop}\{#AppName}"; \
  Filename: "{app}\{#ClientExe}"; \
  IconFilename: "{app}\assets\app_icon.ico"; \
  Tasks: desktopicon

; Server shortcut — Host mode only
Name: "{autoprograms}\{#AppName} Server"; \
  Filename: "{app}\{#ServerExe}"; \
  IconFilename: "{app}\assets\app_icon.ico"; \
  Check: IsHostInstall
Name: "{autodesktop}\{#AppName} Server"; \
  Filename: "{app}\{#ServerExe}"; \
  IconFilename: "{app}\assets\app_icon.ico"; \
  Tasks: desktopicon; \
  Check: IsHostInstall

[Run]
; Launch the client after install
Filename: "{app}\{#ClientExe}"; \
  Description: "Launch {#AppName}"; \
  Flags: nowait postinstall skipifsilent

[Dirs]
; Shared config directory (used by both client and server EXEs)
Name: "{localappdata}\NgweLweSystem"

[UninstallDelete]
Type: files; Name: "{app}\ngwe_lwe.db"
Type: files; Name: "{app}\ngwe_lwe.db-wal"
Type: files; Name: "{app}\ngwe_lwe.db-shm"
Type: files; Name: "{app}\server_config.json"

; ── Pascal Script ─────────────────────────────────────────────
[Code]

var
  InstallTypePage: TInputOptionWizardPage;

{ Called from [Files] Check: and [Icons] Check: }
function IsHostInstall: Boolean;
begin
  Result := InstallTypePage.SelectedValueIndex = 0;
end;

{ Build the custom "Select Installation Type" page }
procedure InitializeWizard;
begin
  InstallTypePage := CreateInputOptionPage(
    wpSelectDir,
    'Select Installation Type',
    'Choose how NgweLwe will be used on this machine.',
    'Installation type:',
    True,   { Exclusive — radio buttons, one choice only }
    False   { not a list box }
  );
  InstallTypePage.Add(
    'Host (Server + Client)  —  Run the server and open the client on this machine'
  );
  InstallTypePage.Add(
    'Client Only  —  Connect to an existing NgweLwe server on the local network'
  );
  { Default to Host }
  InstallTypePage.SelectedValueIndex := 0;
end;

{ Write app_config.json with the correct app_mode after install }
procedure CurStepChanged(CurStep: TSetupStep);
var
  ConfigDir, ConfigFile, AppMode: string;
  Lines: TStringList;
begin
  if CurStep = ssPostInstall then
  begin
    ConfigDir  := ExpandConstant('{localappdata}\NgweLweSystem');
    ConfigFile := ConfigDir + '\app_config.json';
    if not DirExists(ConfigDir) then
      ForceDirectories(ConfigDir);
    if IsHostInstall then
      AppMode := 'host'
    else
      AppMode := 'client';
    Lines := TStringList.Create;
    try
      Lines.Add('{');
      Lines.Add('  "app_mode": "' + AppMode + '"');
      Lines.Add('}');
      Lines.SaveToFile(ConfigFile);
    finally
      Lines.Free;
    end;
  end;
end;
