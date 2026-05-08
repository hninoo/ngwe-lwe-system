; ============================================================
;  NgweLwe — Server Manager Inno Setup Script
;  Requires Inno Setup 6: https://jrsoftware.org/isdl.php
; ============================================================

#define AppName    "NgweLwe"
#define AppVersion "1.0.0-beta"
#define AppExe     "NgweLweServer.exe"
#define AppId      "A2B4C6D8-1E3F-5A7B-9C2D-4E8F0B2C6D0A"

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=NgweLwe

; Install to per-user location — no admin rights needed
DefaultDirName={localappdata}\Programs\{#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Output
OutputDir=installer
OutputBaseFilename=NgweLweServer-v{#AppVersion}-Setup
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

[Files]
; Bundle the entire PyInstaller output directory
Source: "dist\NgweLweServer\*"; \
  DestDir: "{app}"; \
  Flags: ignoreversion recursesubdirs createallsubdirs

; Logo files — skip silently if the folder is empty or missing
Source: "dist\NgweLweServer\assets\logos\*"; \
  DestDir: "{app}\assets\logos"; \
  Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist

[Icons]
; Start Menu
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; \
  IconFilename: "{app}\assets\app_icon.ico"

; Desktop shortcut (if task selected)
Name: "{autodesktop}\{#AppName}";  Filename: "{app}\{#AppExe}"; \
  IconFilename: "{app}\assets\app_icon.ico"; \
  Tasks: desktopicon

[Run]
; Offer to launch after install
Filename: "{app}\{#AppExe}"; \
  Description: "Launch {#AppName}"; \
  Flags: nowait postinstall skipifsilent

[Dirs]
; Shared config directory used by both client and server
Name: "{localappdata}\NgweLweSystem"

[UninstallDelete]
Type: files; Name: "{app}\ngwe_lwe.db"
Type: files; Name: "{app}\ngwe_lwe.db-wal"
Type: files; Name: "{app}\ngwe_lwe.db-shm"
Type: files; Name: "{app}\server_config.json"

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  ConfigDir, ConfigFile: string;
  Lines: TStringList;
begin
  if CurStep = ssPostInstall then
  begin
    ConfigDir  := ExpandConstant('{localappdata}\NgweLweSystem');
    ConfigFile := ConfigDir + '\app_config.json';
    if not DirExists(ConfigDir) then
      ForceDirectories(ConfigDir);
    Lines := TStringList.Create;
    try
      Lines.Add('{');
      Lines.Add('  "app_mode": "host"');
      Lines.Add('}');
      Lines.SaveToFile(ConfigFile);
    finally
      Lines.Free;
    end;
  end;
end;
