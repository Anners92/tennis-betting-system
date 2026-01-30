; Inno Setup Script for Tennis Betting System
; Download Inno Setup from: https://jrsoftware.org/isdl.php

#define MyAppName "Tennis Betting System"
#define MyAppVersion "2.58"
#define MyAppPublisher "Tennis Betting"
#define MyAppExeName "TennisBettingSystem.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={pf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=installer_output
OutputBaseFilename=TennisBettingSystem_Setup_{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "cleandb"; Description: "Start with a clean database (0 bets). Uncheck to keep your current data."; GroupDescription: "Database:"; Flags: unchecked

[Files]
; Include all files from the dist folder (seed database copied to Public Documents on first run)
Source: "dist\TennisBettingSystem\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[InstallDelete]
; If user chose clean database, remove existing DB so the app copies the fresh seed on first launch
Type: files; Name: "{commondocs}\Tennis Betting System\data\tennis_betting.db"; Tasks: cleandb

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
