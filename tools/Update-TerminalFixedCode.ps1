param([Parameter(Mandatory=$true)][ValidatePattern('^[D-Zd-z]:$')][string]$Drive)
$ErrorActionPreference='Stop'
$project=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$source=Join-Path $project 'work\terminal-fixed-code-update'
$stage=Join-Path $project ('work\terminal-fixed-code-install-'+[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ'))
$driveRoot=$Drive.ToUpperInvariant()+'\'
$app=Join-Path $driveRoot 'HOMEBREW\apps\terminal'
function Hash([string]$Path){return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()}
function CheckPath([string]$Path){
 $full=[IO.Path]::GetFullPath($Path)
 if(!$full.StartsWith($driveRoot,[StringComparison]::OrdinalIgnoreCase)){throw 'Path outside selected player'}
 $p=$full
 while($p -and $p.Length -ge $driveRoot.Length){
  if(Test-Path -LiteralPath $p){if(((Get-Item -LiteralPath $p -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){throw 'Linked player path refused'}}
  if($p.TrimEnd('\') -eq $driveRoot.TrimEnd('\')){break};$p=[IO.Path]::GetDirectoryName($p)
 }
 return $full
}
function ConfirmPlayer {
 $logical=Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='$Drive'"
 if(!$logical -or $logical.VolumeName -ne 'WALKMAN' -or $logical.FileSystem -ne 'FAT32' -or [long]$logical.FreeSpace -lt 16777216){throw 'Expected WALKMAN FAT32 volume with free reserve'}
 $sony=$false
 foreach($part in @(Get-CimAssociatedInstance -InputObject $logical -Association Win32_LogicalDiskToPartition)){
  foreach($disk in @(Get-CimAssociatedInstance -InputObject $part -Association Win32_DiskDriveToDiskPartition)){
   if($disk.PNPDeviceID -match '^USBSTOR\\DISK&VEN_SONY&PROD_WALKMAN' -and ([string]$disk.SerialNumber).Trim() -eq '10FA7C05062586'){$sony=$true}
  }
 }
 if(!$sony){throw 'Selected USB device is not the identified X1060'}
}
ConfirmPlayer
$null=CheckPath $app
$ini=Get-Content -LiteralPath (Join-Path $app 'app.ini') -Raw
if($ini -notmatch '(?m)^id=terminal\r?$' -or $ini -notmatch '(?m)^target=sony-nw-x1000-jp\r?$'){throw 'Unexpected installed app target'}
$verified=Get-Content -LiteralPath (Join-Path $source 'verification.json') -Raw | ConvertFrom-Json
if($verified.application_version -ne '0.1.0-dev.22' -or !$verified.fixed_code_implemented){throw 'Wrong update profile'}
foreach($name in @('app','app.ini')){if((Hash (Join-Path $source $name)) -ne $verified.files.$name.sha256){throw 'Frozen source changed'}}
$manifest=Get-Content -LiteralPath (Join-Path $app 'files.sha256')
if($manifest[0] -ne 'HBFILES1'){throw 'Wrong installed file manifest'}
$preserved=[ordered]@{};$names=[Collections.Generic.List[string]]::new()
foreach($line in $manifest | Select-Object -Skip 1){
 if($line -notmatch '^([a-f0-9]{64}) ([0-9]+) ([A-Za-z0-9_.\-/]+)$'){throw 'Invalid installed manifest record'}
 $expected=$Matches[1];$bytes=[long]$Matches[2];$name=$Matches[3]
 if($name.Split('/') -contains '..' -or $names.Contains($name)){throw 'Unsafe/duplicate manifest path'}
 $path=CheckPath (Join-Path $app $name)
 if((Hash $path) -ne $expected -or (Get-Item -LiteralPath $path).Length -ne $bytes){throw "Installed file failed readback: $name"}
 $names.Add($name)
 if($name -notin @('app','app.ini','app-info.json')){$preserved[$path]=$expected}
}
$identity=Join-Path $driveRoot 'HOMEBREW\data\terminal'
if(!(Test-Path -LiteralPath $identity -PathType Container)){$identity=$app}
foreach($name in @('server-cert.der','server-key.der')){$path=CheckPath (Join-Path $identity $name);$preserved[$path]=Hash $path}
$certificate=Join-Path $identity 'server-cert.der';$privateKey=Join-Path $identity 'server-key.der'
if((Get-Item -LiteralPath $privateKey).Length -gt 2048){throw 'Invalid identity key length'}
$pinPath=Join-Path $project 'work\terminal-review\server-cert.sha256'
if((Get-Content -LiteralPath $pinPath -Raw).Trim() -ne (Hash $certificate)){throw 'Player identity differs from the retained PC certificate pin'}
New-Item -ItemType Directory -Path $stage | Out-Null
foreach($name in @('app','app.ini')){Copy-Item -LiteralPath (Join-Path $source $name) -Destination (Join-Path $stage $name)}
$info=Get-Content -LiteralPath (Join-Path $app 'app-info.json') -Raw | ConvertFrom-Json
$info.version='0.1.0-dev.22';$info.changes='Keeps one fixed connection code per personal device identity across restarts and reconnects.'
$utf8=[Text.UTF8Encoding]::new($false)
[IO.File]::WriteAllText((Join-Path $stage 'app-info.json'),($info | ConvertTo-Json -Depth 8)+"`n",$utf8)
$newManifest=[Collections.Generic.List[string]]::new();$newManifest.Add('HBFILES1')
foreach($name in $names){$path=if($name -in @('app','app.ini','app-info.json')){Join-Path $stage $name}else{Join-Path $app $name};$newManifest.Add((Hash $path)+' '+(Get-Item -LiteralPath $path).Length+' '+$name)}
[IO.File]::WriteAllText((Join-Path $stage 'files.sha256'),($newManifest -join "`n")+"`n",$utf8)
$launcher=CheckPath (Join-Path $driveRoot 'HOMEBREW\launcher\app');$launcherBefore=Hash $launcher
$changed=[Collections.Generic.List[object]]::new()
foreach($name in @('app','app.ini','app-info.json','files.sha256')){
 ConfirmPlayer;$dest=CheckPath (Join-Path $app $name);$inputPath=Join-Path $stage $name;$sha=Hash $inputPath
 $temporary=$dest+'.fixed-code-'+[Guid]::NewGuid().ToString('N')+'.tmp'
 $stream=[IO.FileStream]::new($temporary,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None,65536,[IO.FileOptions]::WriteThrough)
 try{$payload=[IO.File]::ReadAllBytes($inputPath);$stream.Write($payload,0,$payload.Length);$stream.Flush($true)}finally{$stream.Dispose()}
 if((Hash $temporary) -ne $sha){throw 'Temporary write verification failed'}
 ConfirmPlayer;[IO.File]::Move($temporary,$dest,$true)
 if((Hash $dest) -ne $sha){throw 'Final write verification failed'}
 $changed.Add([ordered]@{file=$name;bytes=(Get-Item -LiteralPath $dest).Length;sha256=$sha})
}
foreach($path in $preserved.Keys){if((Hash $path) -ne $preserved[$path]){throw 'Preserved identity/resource changed'}}
if((Hash $launcher) -ne $launcherBefore){throw 'Launcher unexpectedly changed'}
$keyBytes=[IO.File]::ReadAllBytes($privateKey);$hmac=[Security.Cryptography.HMACSHA256]::new($keyBytes)
try{$digest=$hmac.ComputeHash([Text.Encoding]::ASCII.GetBytes('X1000-WIFI-TERMINAL-CODE-v1'));$code=([BitConverter]::ToString($digest,0,16)).Replace('-','').ToLowerInvariant()}finally{$hmac.Dispose();[Array]::Clear($keyBytes,0,$keyBytes.Length)}
$codeFile=Join-Path $project 'work\terminal-live\session-code.private.txt'
[IO.File]::WriteAllText($codeFile,$code,[Text.Encoding]::ASCII)
[IO.File]::WriteAllText((Join-Path $project 'work\terminal-live\fixed-device-code.private.txt'),$code,[Text.Encoding]::ASCII)
$report=[ordered]@{success=$true;version='0.1.0-dev.22';drive=$Drive;changed_files=@($changed.ToArray());pairing_identity_preserved=$true;resources_preserved=$true;launcher_unchanged=$true;fixed_code_saved_on_pc=$true;code_printed=$false;system_partition_written=$false;firmware_written=$false;device_program_executed=$false;runtime_verified=$false}
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $stage 'install-report.json') -Encoding utf8
$report | ConvertTo-Json -Depth 8
