; DYS-fr Windows installer.
;
; Ships a self-contained install: the PyInstaller runtime plus the JRE, LanguageTool
; and the spaCy model. It deliberately does NOT include the Mistral GGUF (~4.1 GB);
; that model is downloaded from inside the application on demand.
;
; Requires Inno Setup 6.3 or newer (for "x64compatible").
; Invoked by packaging/windows/build.ps1 with -Channel installer.

#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
#ifndef RuntimeDir
  #define RuntimeDir "..\..\build\pyinstaller-runtime\DYS-fr-runtime"
#endif
#ifndef StageDir
  #define StageDir "..\..\build\staging\hybrid"
#endif
#ifndef OutputDir
  #define OutputDir "..\..\build\installer"
#endif

#define AppExe "DYS-fr-runtime.exe"
; Must match APP_MUTEX_NAME in src/runtime/launcher.py.
; No braces: Inno treats { in a directive value as a constant reference.
#define AppMutexName "DYS-fr-8EFBD1E9-CC98-4D95-8C98-D0C7F0A0E6E8"

[Setup]
AppId={{8EFBD1E9-CC98-4D95-8C98-D0C7F0A0E6E8}
AppName=DYS-fr
AppVersion={#AppVersion}
AppVerName=DYS-fr {#AppVersion}
AppPublisher=DYS-fr
VersionInfoVersion={#AppVersion}
DefaultDirName={autopf}\DYS-fr
DefaultGroupName=DYS-fr
DisableProgramGroupPage=yes
AllowNoIcons=yes
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName=DYS-fr
SetupIconFile=..\..\src\ui\img\logo.ico
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
PrivilegesRequired=admin
; Empty: no /CURRENTUSER fallback, so the layout is always per-machine.
PrivilegesRequiredOverridesAllowed=
; Measured: lzma2/max + solid over ~1.1 GB took 8h06m on a developer machine for a
; 507 MB installer. Pass /DFastCompression (build.ps1 -FastCompression) while iterating.
#ifdef FastCompression
Compression=lzma2/fast
SolidCompression=no
#else
Compression=lzma2/max
SolidCompression=yes
#endif
LZMAUseSeparateProcess=yes
OutputDir={#OutputDir}
OutputBaseFilename=DYS-fr-Setup-{#AppVersion}
OutputManifestFile={#OutputDir}\DYS-fr-Setup-{#AppVersion}-files.txt
SetupLogging=yes
; AppMutex gives a polite "please close DYS-fr" prompt before any file is touched;
; CloseApplications is the backstop that catches the java.exe child, whose exe lives
; under {app}\_internal\runtime\jre\bin. Neither alone is sufficient.
AppMutex={#AppMutexName}
CloseApplications=yes
CloseApplicationsFilter=*.exe,*.dll,*.jar
; Deliberately no: RestartApplications=yes would relaunch the app under the elevated
; installer token, which resolves the wrong %LOCALAPPDATA%.
RestartApplications=no
UsePreviousAppDir=yes

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[InstallDelete]
; Inno never removes orphans on upgrade. Without this, a dependency dropped between
; versions leaves a stale .pyd/.dll that PyInstaller's import machinery may still pick
; up. Costs a full rewrite per upgrade; correctness wins for a product shipped rarely.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
; 1) PyInstaller onedir bundle -> {app}\DYS-fr-runtime.exe + {app}\_internal\**
Source: "{#RuntimeDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; 2) Staged heavy assets -> {app}\_internal\resources\**
;    Excludes models\ so a stale stage root can never smuggle in the 4.1 GB GGUF.
;    build.ps1 also hard-fails on this; belt and braces.
Source: "{#StageDir}\resources\*"; DestDir: "{app}\_internal\resources"; Excludes: "\models\*"; Flags: ignoreversion recursesubdirs createallsubdirs

; 3) Embedded JRE -> {app}\_internal\runtime\jre\**
Source: "{#StageDir}\runtime\jre\*"; DestDir: "{app}\_internal\runtime\jre"; Flags: ignoreversion recursesubdirs createallsubdirs

; 4) Build provenance, for support: records detected JRE/LT/spaCy versions.
Source: "{#StageDir}\staging-manifest.json"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\DYS-fr"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"
Name: "{group}\Désinstaller DYS-fr"; Filename: "{uninstallexe}"
Name: "{autodesktop}\DYS-fr"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
; runasoriginaluser is essential: setup runs elevated, and without this the first
; launch would run as the administrator and write its state (instance lock, config,
; downloaded models) into that account's %LOCALAPPDATA% instead of the user's.
Filename: "{app}\{#AppExe}"; Description: "Lancer DYS-fr"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent runasoriginaluser

[UninstallDelete]
; Catch-all so anything written under {app} at runtime cannot orphan the directory.
Type: filesandordirs; Name: "{app}\_internal"
Type: filesandordirs; Name: "{app}"

[Code]
{ Inno Setup has no built-in command-line lookup; ParamCount/ParamStr is the idiom. }
function CmdLineParamExists(const Value: String): Boolean;
var
  I: Integer;
begin
  Result := False;
  for I := 1 to ParamCount do
    if CompareText(ParamStr(I), Value) = 0 then
    begin
      Result := True;
      Exit;
    end;
end;

function UserDataRoot(): String;
begin
  Result := ExpandConstant('{localappdata}') + '\DYS-fr';
end;

function WantsPurge(): Boolean;
begin
  if CmdLineParamExists('/PURGEDATA') then begin Result := True; Exit; end;
  if CmdLineParamExists('/KEEPDATA') then begin Result := False; Exit; end;
  if UninstallSilent() then begin Result := False; Exit; end;

  { Defaults to "Non": never destroy a 4 GB download on a stray Enter. }
  Result := MsgBox(
    'Supprimer également vos données personnelles ?' + #13#10 + #13#10 +
    'Cela effacera :' + #13#10 +
    '  - le modèle IA téléchargé (environ 4 Go)' + #13#10 +
    '  - vos préférences (config.yaml)' + #13#10 + #13#10 +
    'Choisissez « Non » pour les conserver en vue d''une réinstallation.',
    mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Root: String;
begin
  if CurUninstallStep <> usUninstall then
    Exit;

  Root := UserDataRoot();

  { Always removed: volatile state and caches, none of which the user authored. }
  DelTree(Root + '\run', True, True, True);
  DelTree(Root + '\spacy-cache', True, True, True);
  DelTree(Root + '\logs', True, True, True);
  { Legacy cache directory written by pre-0.1.0 builds; no current code uses it. }
  DelTree(Root + '\spacy_models', True, True, True);
  { Fallback location used when %LOCALAPPDATA% is not writable (src/utils/paths.py). }
  DelTree(ExpandConstant('{tmp}') + '\..\dys-fr\run', True, True, True);

  if WantsPurge() then
  begin
    DelTree(Root + '\models', True, True, True);
    DeleteFile(Root + '\config.yaml');
  end;

  { No-op unless it is now empty. }
  RemoveDir(Root);
end;
