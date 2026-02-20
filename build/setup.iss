; Inno Setup 6+ — YT Downloader Installer
; Запуск: iscc build\setup.iss  (из корня проекта)

#define AppName      "YT Downloader"
#define AppVersion   "0.1.0"
#define AppPublisher "YTDownloader"
#define AppURL       "https://github.com/your-repo/youtube_downloader"
#define AppExeName   "YTDownloader.exe"
#define DistDir      "..\dist\YTDownloader"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=..\dist\installer
OutputBaseFilename=YTDownloader-{#AppVersion}-setup
SetupIconFile=..\resources\icons\app.ico
WizardImageFile=..\resources\installer\wizard.png
WizardSmallImageFile=..\resources\installer\small.png
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
PrivilegesRequired=admin

[Languages]
Name: "russian";  MessagesFile: "compiler:Languages\Russian.isl"
Name: "english";  MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительные задачи:"; Flags: unchecked

[Files]
; Основной EXE
Source: "{#DistDir}\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; Python runtime + PySide6 (LGPLv3) — всё в _internal/
Source: "{#DistDir}\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs

; FFmpeg (LGPLv3) — ВНЕ _internal, заменяемые бинарники
Source: "{#DistDir}\vendor\ffmpeg\bin\ffmpeg.exe";  DestDir: "{app}\vendor\ffmpeg\bin"; Flags: ignoreversion
Source: "{#DistDir}\vendor\ffmpeg\bin\ffprobe.exe"; DestDir: "{app}\vendor\ffmpeg\bin"; Flags: ignoreversion
Source: "{#DistDir}\vendor\ffmpeg\bin\ffplay.exe";  DestDir: "{app}\vendor\ffmpeg\bin"; Flags: ignoreversion

; Лицензии
Source: "{#DistDir}\licenses\*"; DestDir: "{app}\licenses"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}";         Filename: "{app}\{#AppExeName}"
Name: "{group}\Удалить {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}";   Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Запустить {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Удалять конфиги и данные — только если пользователь согласен
; (для безопасности НЕ удаляем %APPDATA%\YTDownloader автоматически)
