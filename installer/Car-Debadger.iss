#define MyAppName "FiveM Vehicle Debadger"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Car-Debadger"
#define MyAppExeName "Car-Debadger.exe"

[Setup]
AppId={{6D56A814-1D2E-4E6B-96A8-CA7D28A8B1E4}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Car-Debadger
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist\installer
OutputBaseFilename=Car-Debadger-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#MyAppExeName}

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\Car-Debadger\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\FiveM Vehicle Debadger"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\FiveM Vehicle Debadger"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch FiveM Vehicle Debadger"; Flags: postinstall nowait skipifsilent
