; ============================================================
;  Ngwe Lwe System — Server Inno Setup Script
; ============================================================

#define AppName    "Ngwe Lwe Server"
#define AppVersion "1.0.0"
#define AppExe     "NgweLweServer.exe"
#define AppId      "A2B4C6D8-1E3F-5A7B-9C2D-4E8F0B2C6D0A"

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Ngwe Lwe System
DefaultDirName={localappdata}\Programs\{#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

OutputDir=installer
OutputBaseFilename=NgweLweServer-Setup-v{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExe}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; \
  Description: "Create a &desktop shortcut"; \
  GroupDescription: "Additional icons:"

[Files]
Source: "dist\NgweLweServer\*"; \
  DestDir: "{app}"; \
  Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}";  Filename: "{app}\{#AppExe}"; \
  Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; \
  Description: "Launch {#AppName}"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{app}\ngwe_lwe.db"
Type: files; Name: "{app}\ngwe_lwe.db-wal"
Type: files; Name: "{app}\ngwe_lwe.db-shm"
Type: files; Name: "{app}\server_config.json"
