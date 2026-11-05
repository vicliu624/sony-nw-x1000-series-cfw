param([Parameter(Mandatory)][string]$RepairDirectory,
      [Parameter(Mandatory)][ValidatePattern('^[D-Zd-z]:$')][string]$Drive,
      [Parameter(Mandatory)][ValidatePattern('^[A-Za-z0-9_-]+$')][string]$ExpectedSerial)
$ErrorActionPreference='Stop'
$reviewRoot=[IO.Path]::GetFullPath($RepairDirectory)
$project=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if(!$reviewRoot.StartsWith((Join-Path $project 'work/'),[StringComparison]::OrdinalIgnoreCase)){throw 'Repair must use private project work inputs'}
$review=Get-Content -LiteralPath (Join-Path $reviewRoot 'review.json') -Raw|ConvertFrom-Json
if(!$review.prepared -or !$review.metadata_only -or !$review.executables_unchanged -or $review.id -ne 'espnow-chat' -or $review.version -ne '0.1.0-dev.2'){throw 'Unexpected repair scope'}
$driveRoot=$Drive+'\';$chat=Join-Path $driveRoot 'HOMEBREW/apps/espnow-chat'
$raw=Join-Path $driveRoot 'HOMEBREW/apps/espnow-test';$tools=Join-Path $driveRoot 'HOMEBREW/tools';$destination=Join-Path $tools 'espnow-test'
function Hash([string]$Path){return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()}
function Confirm-Walkman {
 $logical=Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='$Drive'"
 if(!$logical -or $logical.VolumeName -ne 'WALKMAN' -or $logical.FileSystem -ne 'FAT32' -or [long]$logical.FreeSpace -lt 1048576){throw 'WALKMAN volume/space check failed'}
 $sonyDiskCount=0
 foreach($part in @(Get-CimAssociatedInstance -InputObject $logical -Association Win32_LogicalDiskToPartition)){
  foreach($disk in @(Get-CimAssociatedInstance -InputObject $part -Association Win32_DiskDriveToDiskPartition)){
   if($disk.PNPDeviceID -match '^USBSTOR\\DISK&VEN_SONY&PROD_WALKMAN' -and ([string]$disk.SerialNumber).Trim() -eq $ExpectedSerial){$sonyDiskCount++}
  }
 }
 if($sonyDiskCount -ne 1){throw 'Selected Sony disk identity changed'}
}
function Plain([string]$Path){
 $full=[IO.Path]::GetFullPath($Path)
 if(!$full.StartsWith($driveRoot,[StringComparison]::OrdinalIgnoreCase)){throw 'Target escaped selected drive'}
 $probe=$full
 while($probe){
  if(Test-Path -LiteralPath $probe){if((Get-Item -LiteralPath $probe -Force).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Reparse path refused'}}
  $next=[IO.Path]::GetDirectoryName($probe);if($next -eq $probe){break};$probe=$next
 }
}
function Write-Checked([string]$Source,[string]$Target,[string]$Expected,[bool]$Replace){
 Confirm-Walkman;Plain $Target
 $temp=$Target+'.repair-'+[Guid]::NewGuid().ToString('N')
 $inputStream=$null;$outputStream=$null
 try {
  try {
   $inputStream=[IO.FileStream]::new($Source,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
   $outputStream=[IO.FileStream]::new($temp,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None,65536,[IO.FileOptions]::WriteThrough)
   $inputStream.CopyTo($outputStream);$outputStream.Flush($true)
  } finally {if($outputStream){$outputStream.Dispose()};if($inputStream){$inputStream.Dispose()}}
  if((Hash $temp) -ne $Expected){throw 'Repair readback failed'}
  Confirm-Walkman;Plain $Target;[IO.File]::Move($temp,$Target,$Replace)
 } finally {if(Test-Path -LiteralPath $temp){Plain $temp;Remove-Item -LiteralPath $temp -Force}}
}
$added=[Collections.Generic.List[string]]::new();$inventoryCommitted=$false;$moved=$false
$launcher=Join-Path $driveRoot 'HOMEBREW/launcher/app';$launcherBefore=$null
try {
 Confirm-Walkman;Plain $chat;Plain $raw;Plain $destination
 $launcherBefore=Hash $launcher
 foreach($name in @('app','radio-worker','app.ini')){
  if((Hash (Join-Path $chat $name)) -ne $review.files.$name.sha256){throw 'Installed Chat program changed; refusing metadata repair'}
 }
 if((Hash (Join-Path $chat 'files.sha256')) -ne $review.old_inventory_sha256){throw 'Installed Chat inventory changed'}
 $metadata=@('app-info.json','presentation.bin','icon.png','icon.svg')
 foreach($name in $metadata){if(Test-Path -LiteralPath (Join-Path $chat $name)){throw 'Unexpected existing metadata; re-audit first'}}
 foreach($property in $review.files.PSObject.Properties){
  $source=Join-Path $reviewRoot ('package/'+$property.Name)
  if($property.Name -notin @('app','radio-worker','app.ini','files.sha256','app-info.json','presentation.bin','icon.png','icon.svg') -or (Hash $source) -ne $property.Value.sha256){throw 'Frozen repair input changed'}
 }
 if(Test-Path -LiteralPath $destination){throw 'Tool destination already exists'}
 if(Test-Path -LiteralPath (Join-Path $raw 'app.ini')){throw 'ESP-NOW test has become a registered application'}
 $rawFiles=@(Get-ChildItem -LiteralPath $raw -Force)
 if($rawFiles.Count -ne 3 -or @($rawFiles|Where-Object {$_.PSIsContainer -or $_.Name -notin @('espnow-test.arm','espnow-test-alpha2.arm','espnow-test-alpha3.arm')}).Count){throw 'Unexpected CLI-tool contents'}
 $rawHashes=@{};foreach($file in $rawFiles){Plain $file.FullName;$rawHashes[$file.Name]=Hash $file.FullName}
 foreach($name in $metadata){
  Write-Checked (Join-Path $reviewRoot ('package/'+$name)) (Join-Path $chat $name) $review.files.$name.sha256 $false
  $added.Add($name)
 }
 Write-Checked (Join-Path $reviewRoot 'package/files.sha256') (Join-Path $chat 'files.sha256') $review.files.'files.sha256'.sha256 $true
 $inventoryCommitted=$true
 Confirm-Walkman;Plain $tools
 if(!(Test-Path -LiteralPath $tools)){$null=New-Item -ItemType Directory -Path $tools}
 foreach($name in $rawHashes.Keys){if((Hash (Join-Path $raw $name)) -ne $rawHashes[$name]){throw 'CLI-tool content changed before move'}}
 # Both absolute paths are on the verified user volume; no overwrite/merge.
 Plain $raw;Plain $destination;[IO.Directory]::Move($raw,$destination);$moved=$true
 foreach($name in $rawHashes.Keys){if((Hash (Join-Path $destination $name)) -ne $rawHashes[$name]){throw 'Moved CLI-tool verification failed'}}
 foreach($property in $review.files.PSObject.Properties){if((Hash (Join-Path $chat $property.Name)) -ne $property.Value.sha256){throw 'Final Chat readback failed'}}
 if((Hash $launcher) -ne $launcherBefore){throw 'Launcher changed unexpectedly'}
 $report=[ordered]@{success=$true;metadata_updated=@($added.ToArray());chat_version='0.1.0-dev.2';chat_executables_unchanged=$true;tools_moved=$moved;tool_files_preserved=$rawHashes.Count;launcher_unchanged=$true;firmware_written=$false;account_or_rom_data_written=$false}
 $report|ConvertTo-Json -Depth 4|Set-Content -LiteralPath (Join-Path $reviewRoot 'install-report.json') -Encoding utf8
 $report|ConvertTo-Json -Depth 4
} catch {
 if(!$inventoryCommitted){foreach($name in $added){$path=Join-Path $chat $name;if((Hash $path) -eq $review.files.$name.sha256){Plain $path;Remove-Item -LiteralPath $path -Force}}}
 [ordered]@{success=$false;error=$_.Exception.Message;inventory_committed=$inventoryCommitted;tools_moved=$moved;firmware_written=$false}|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $reviewRoot 'install-failure.json') -Encoding utf8
 throw
}
