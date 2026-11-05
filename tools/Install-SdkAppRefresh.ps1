param([Parameter(Mandatory)][string]$PlanPath,
 [Parameter(Mandatory)][ValidatePattern('^[D-Zd-z]:$')][string]$Drive,
 [Parameter(Mandatory)][ValidatePattern('^[A-Za-z0-9_-]+$')][string]$ExpectedSerial)
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($PlanPath))
$project=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if(!$root.StartsWith((Join-Path $project 'work/'),[StringComparison]::OrdinalIgnoreCase)){throw 'Private project staging required'}
$plan=Get-Content -LiteralPath $PlanPath -Raw|ConvertFrom-Json
if($plan.schema -ne 'x1000-sdk-app-refresh-v1' -or $plan.sdk -ne '0.2.0-alpha.9'){throw 'Unexpected update plan'}
$volume=$Drive+'\';$playerHomeRoot=Join-Path $volume 'HOMEBREW'
$stage=Join-Path $playerHomeRoot ('.sdk-update-'+[Guid]::NewGuid().ToString('N'))
$committed=[Collections.Generic.List[string]]::new();$launcherCommitted=$false
function Hash([string]$Path){return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()}
function Confirm-Volume {
 $logical=Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='$Drive'"
 if(!$logical -or $logical.VolumeName -ne 'WALKMAN' -or $logical.FileSystem -ne 'FAT32' -or [long]$logical.FreeSpace -lt ([long]$plan.total_new_bytes+16777216)){throw 'WALKMAN volume/space check failed'}
 $sonyDiskCount=0
 foreach($part in @(Get-CimAssociatedInstance -InputObject $logical -Association Win32_LogicalDiskToPartition)){
  foreach($disk in @(Get-CimAssociatedInstance -InputObject $part -Association Win32_DiskDriveToDiskPartition)){
   if($disk.PNPDeviceID -match '^USBSTOR\\DISK&VEN_SONY&PROD_WALKMAN' -and ([string]$disk.SerialNumber).Trim() -eq $ExpectedSerial){$sonyDiskCount++}
  }
 }
 if($sonyDiskCount -ne 1){throw 'Sony disk identity changed'}
}
function Plain([string]$Path){
 $full=[IO.Path]::GetFullPath($Path)
 if(!$full.StartsWith($volume,[StringComparison]::OrdinalIgnoreCase)){throw 'Device path escaped selected volume'}
 $probe=$full
 while($probe){if(Test-Path -LiteralPath $probe){if((Get-Item -LiteralPath $probe -Force).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Reparse path refused'}};$probe=[IO.Path]::GetDirectoryName($probe)}
}
function Relative([string]$Name){
 if($Name -notmatch '^(apps/[a-z0-9][a-z0-9-]{0,31}/[A-Za-z0-9_./-]+|launcher/app)$' -or ($Name -split '/') -contains '..' -or ($Name -split '/') -contains '.'){throw 'Unexpected package path'}
 if($Name.StartsWith('apps/') -and ($Name -split '/')[1] -notin @($plan.apps.id)){throw 'App not in selected update set'}
}
function Copy-Checked([string]$Source,[string]$Destination,[string]$Expected){
 Confirm-Volume;Plain $Destination
 $null=New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($Destination)) -Force
 $inputStream=$null;$outputStream=$null
 try {
  $inputStream=[IO.FileStream]::new($Source,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
  $outputStream=[IO.FileStream]::new($Destination,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None,65536,[IO.FileOptions]::WriteThrough)
  $inputStream.CopyTo($outputStream);$outputStream.Flush($true)
 } finally {if($outputStream){$outputStream.Dispose()};if($inputStream){$inputStream.Dispose()}}
 if((Hash $Destination) -ne $Expected){throw 'Staged file readback failed'}
}
try {
 Confirm-Volume;Plain $playerHomeRoot
 foreach($row in $plan.old_files){
  Relative $row.relative;$device=Join-Path $playerHomeRoot $row.relative;Plain $device
  if((Hash $device) -ne $row.sha256 -or (Hash (Join-Path $root ('previous/'+$row.relative))) -ne $row.sha256){throw 'Old package changed or rollback copy invalid'}
 }
 foreach($app in $plan.apps){
  $path=Join-Path $playerHomeRoot ('apps/'+$app.id);Plain $path
  $actual=@(Get-ChildItem -LiteralPath $path -Recurse -Force -File)
  $expected=@($plan.old_files|Where-Object {$_.relative.StartsWith('apps/'+$app.id+'/')})
  if($actual.Count -ne $expected.Count){throw 'Unindexed user file in application directory'}
 }
 foreach($row in $plan.new_files){Relative $row.relative;if((Hash (Join-Path $root ('new/'+$row.relative))) -ne $row.sha256){throw 'Frozen update source changed'}}
 $null=New-Item -ItemType Directory -Path $stage
 foreach($row in $plan.new_files){Copy-Checked (Join-Path $root ('new/'+$row.relative)) (Join-Path $stage ('new/'+$row.relative)) $row.sha256}
 $oldLauncher=($plan.old_files|Where-Object {$_.relative -eq 'launcher/app'}).sha256
 Copy-Checked (Join-Path $root 'previous/launcher/app') (Join-Path $stage 'previous/launcher/app') $oldLauncher
 Confirm-Volume
 [IO.File]::Move((Join-Path $stage 'new/launcher/app'),(Join-Path $playerHomeRoot 'launcher/app'),$true);$launcherCommitted=$true
 foreach($app in $plan.apps){
  Confirm-Volume;$active=Join-Path $playerHomeRoot ('apps/'+$app.id);$old=Join-Path $stage ('previous/apps/'+$app.id);$incoming=Join-Path $stage ('new/apps/'+$app.id)
  Plain $active;Plain $old;Plain $incoming;$null=New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($old)) -Force
  [IO.Directory]::Move($active,$old)
  try {[IO.Directory]::Move($incoming,$active)} catch {if(!(Test-Path -LiteralPath $active)){[IO.Directory]::Move($old,$active)};throw}
  $committed.Add($app.id)
 }
 foreach($row in $plan.new_files){if((Hash (Join-Path $playerHomeRoot $row.relative)) -ne $row.sha256){throw 'Final installed hash mismatch'}}
 $full=[IO.Path]::GetFullPath($stage)
 if([IO.Path]::GetDirectoryName($full) -ne [IO.Path]::GetFullPath($playerHomeRoot) -or [IO.Path]::GetFileName($full) -notmatch '^\.sdk-update-[0-9a-f]{32}$'){throw 'Unsafe staging cleanup path'}
 Plain $full;Remove-Item -LiteralPath $full -Recurse -Force
 $result=[ordered]@{installed=$true;sdk=$plan.sdk;apps=@($plan.apps);byte_identical_apps=@($plan.unchanged).Count;launcher_version=$plan.launcher_version;account_rom_save_paths_written=$false;firmware_written=$false;temporary_stage_removed=$true}
 $result|ConvertTo-Json -Depth 6|Set-Content (Join-Path $root 'install-result.private.json') -Encoding utf8
 $result|ConvertTo-Json -Depth 6
} catch {
 $reason=$_.Exception.Message;$rollbackErrors=@()
 for($index=$committed.Count-1;$index -ge 0;$index--){
  $id=$committed[$index];$active=Join-Path $playerHomeRoot ('apps/'+$id);$old=Join-Path $stage ('previous/apps/'+$id);$failed=Join-Path $stage ('failed/apps/'+$id)
  try {Confirm-Volume;Plain $active;Plain $old;Plain $failed;$null=New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($failed)) -Force;[IO.Directory]::Move($active,$failed);[IO.Directory]::Move($old,$active)} catch {$rollbackErrors+=$_.Exception.Message}
 }
 if($launcherCommitted){try {Confirm-Volume;[IO.File]::Move((Join-Path $stage 'previous/launcher/app'),(Join-Path $playerHomeRoot 'launcher/app'),$true)} catch {$rollbackErrors+=$_.Exception.Message}}
 [ordered]@{installed=$false;error=$reason;rollback_errors=$rollbackErrors;stage=$stage;firmware_written=$false}|ConvertTo-Json -Depth 4|Set-Content (Join-Path $root 'install-failure.private.json') -Encoding utf8
 throw
}
