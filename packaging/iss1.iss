; Inno Setup script for SimpleTranslator
; Build steps:
;   1. pyinstaller packaging\SimpleTranslator.spec
;   2. iscc packaging\iss1.iss

#define MyAppName "SimpleTranslator"
#define MyAppVersion "1.1.0"
#define MyAppPublisher "Kailiang Chen"
#define MyAppExeName "SimpleTranslator.exe"
#define MyProjectDir "E:\work\simpletranslator"
#define MyBuildDir MyProjectDir + "\dist\SimpleTranslator"

[Setup]
AppId={{D428C5A8-E8F8-4CD1-996F-B677A575A246}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir={#MyProjectDir}\release
OutputBaseFilename={#MyAppName}_Setup_{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "{#MyBuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Parameters: "--lang {code:GetLangCode}"; Flags: nowait postinstall skipifsilent

[Code]
// Return the two-letter language code chosen by the user in the installer.
function GetLangCode(Param: String): String;
begin
  if ActiveLanguage = 'chinesesimplified' then
    Result := 'zh'
  else
    Result := 'en';
end;

// Write the installer language choice to language.json so the app
// starts in the same language the user selected during installation.
procedure CurStepChanged(CurStep: TSetupStep);
var
  Lang: String;
  Code: String;
  Dir: String;
begin
  if CurStep = ssPostInstall then
  begin
    Code := GetLangCode('');
    Dir := ExpandConstant('{app}\config');
    ForceDirectories(Dir);
    Lang := '{"language": "' + Code + '"}';
    SaveStringToFile(Dir + '\language.json', Lang, False);
  end;
end;
