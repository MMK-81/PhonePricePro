; Inno Setup 6 script for PhonePricePro
#define MyAppName "PhonePricePro"
#define MyAppNameFa "قیمت یار"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "محمد مهدی کاشی"
#define MyAppExeName "PhonePricePro.exe"

[Setup]
AppId={{A7F3C1D9-5E42-4C88-9A1B-6F72D81C0E44}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppNameFa} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppNameFa}
OutputDir=installer_output
OutputBaseFilename=PhonePricePro_Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=assets\app.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
Source: "dist\PhonePricePro\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppNameFa}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppNameFa}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppNameFa}"; Flags: nowait postinstall skipifsilent
