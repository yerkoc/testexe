#define MyAppName "Test EXE"
#ifndef MyAppVersion
#define MyAppVersion "0.0.0"
#endif

[Setup]
AppId={{7D0A46E4-52E2-47A6-8615-8D2F3B8B6E17}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=yerkoc
DefaultDirName={localappdata}\Programs\TestEXE
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=TestEXE-Setup-{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
CloseApplications=yes
RestartApplications=no
UninstallDisplayName={#MyAppName}

[Tasks]
Name: "desktopicon"; Description: "Masaustu kisayolu olustur"; GroupDescription: "Ek gorevler:"; Flags: unchecked

[Files]
Source: "dist\TestEXE.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\TestEXE.exe"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\TestEXE.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\TestEXE.exe"; Description: "{#MyAppName} uygulamasini baslat"; Flags: nowait postinstall skipifsilent
