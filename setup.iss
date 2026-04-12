; ============================================================
;  Ngwe Lwe System — Inno Setup Script
;  Requires Inno Setup 6: https://jrsoftware.org/isdl.php
; ============================================================

#define AppName    "Ngwe Lwe System"
#define AppVersion "1.0.1"
#define AppExe     "NgweLweSystem.exe"
#define AppId      "B5A3C8D2-9F1E-4A7B-8C3D-2E6F0A1B4C5D"

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Ngwe Lwe System
AppPublisherURL=

; Install to per-user location — no admin rights needed
DefaultDirName={localappdata}\Programs\{#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Output
OutputDir=installer
OutputBaseFilename=NgweLweSystem-Setup-v{#AppVersion}
Compression=lzma2
SolidCompression=yes

; Wizard appearance
WizardStyle=modern
WizardSizePercent=100

; Uninstall
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExe}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; \
  Description: "Create a &desktop shortcut"; \
  GroupDescription: "Additional icons:"

[Files]
; Bundle the entire PyInstaller output directory
Source: "dist\NgweLweSystem\*"; \
  DestDir: "{app}"; \
  Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Start Menu
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"

; Desktop shortcut (if task selected)
Name: "{autodesktop}\{#AppName}";  Filename: "{app}\{#AppExe}"; \
  Tasks: desktopicon

[Run]
; Offer to launch after install
Filename: "{app}\{#AppExe}"; \
  Description: "Launch {#AppName}"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Remove the auto-created database when uninstalling
Type: files; Name: "{app}\ngwe_lwe.db"
Type: files; Name: "{app}\ngwe_lwe.db-wal"
Type: files; Name: "{app}\ngwe_lwe.db-shm"
