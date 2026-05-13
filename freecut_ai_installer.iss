; ---------------------------------------------------------------------------
; FreeCut AI — Inno Setup installer script (Windows)
; Install Inno Setup: https://jrsoftware.org/isinfo.php
; Build: iscc freecut_ai_installer.iss
; ---------------------------------------------------------------------------

#define AppName    "FreeCut AI"
#define AppVersion "1.0.0"
#define AppPublisher "FreeCut AI"
#define AppURL     "https://freecut.ai"
#define AppExeName "FreeCut AI.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
; Uncomment the next line to require admin rights
; PrivilegesRequired=admin
OutputDir=dist
OutputBaseFilename=FreeCutAI-Setup-{#AppVersion}
; IconFilename=assets\app.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Include entire PyInstaller output folder
Source: "dist\{#AppName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}";       Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
