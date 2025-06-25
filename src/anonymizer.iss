[Setup]
AppName=Anonymizer
AppVersion=1.0.0
DefaultDirName={pf}\Anonymizer
DefaultGroupName=Anonymizer
UninstallDisplayIcon={app}\Anonymizer.exe
OutputDir=dist_installer
OutputBaseFilename=Anonymizer_Installer
Compression=lzma
SolidCompression=yes

[Files]
[Files]
Source: "Z:\home\fhartmann\projects\LAI-anonymizer\dist\Anonymizer\*"; DestDir: "{app}"; Flags: recursesubdirs
[Icons]
Name: "{group}\Anonymizer"; Filename: "{app}\Anonymizer.exe"

[Run]
Filename: "{app}\Anonymizer.exe"; Description: "Launch Anonymizer"; Flags: nowait postinstall skipifsilent
