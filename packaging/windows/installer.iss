#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

#ifndef AppDistDir
  #define AppDistDir "..\..\build\pyinstaller-dist\DYS-fr"
#endif

#ifndef OutputDir
  #define OutputDir "..\..\build\installer"
#endif

[Setup]
AppId={{8EFBD1E9-CC98-4D95-8C98-D0C7F0A0E6E8}
AppName=DYS-fr
AppVersion={#AppVersion}
AppPublisher=DYS-fr
DefaultDirName={autopf}\DYS-fr
DefaultGroupName=DYS-fr
UninstallDisplayIcon={app}\DYS-fr.exe
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
DisableProgramGroupPage=yes
AllowNoIcons=yes
OutputDir={#OutputDir}
OutputBaseFilename=DYS-fr-Setup-{#AppVersion}
SetupLogging=yes

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le Bureau"; GroupDescription: "Raccourcis :"; Flags: unchecked

[Files]
Source: "{#AppDistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\DYS-fr"; Filename: "{app}\DYS-fr.exe"
Name: "{autodesktop}\DYS-fr"; Filename: "{app}\DYS-fr.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\DYS-fr.exe"; Description: "Lancer DYS-fr"; Flags: nowait postinstall skipifsilent
