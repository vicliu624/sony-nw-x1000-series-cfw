param([ValidateSet('Preview','Install','Restore')][string]$Mode='Preview')
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
# Narrow temporary diagnostic only. Default is read-only with PC-side reports.
# This script never executes device code, sends USB commands or flashes firmware.
$project=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$originalHash='0be950324a42eed4c5976d50bca6b7eca4bf057557a8898aa188afb12e9c0d6b'
$captureHash='1dad624e401b376b3b445344ed90ad3492e8add60f1eaf8740476d22830446a1'
$childHash='e6885c569adc44af7f6d78870ca5bdfac1e82f55f141c6c028814dbbbb07e663'
$seedHash='3ebbd00e2e39106c3871c96ac50f9cea2b0e6e74d0e170fbd20c9cd5b9d89978'
$capture=Join-Path $project 'work/launcher-capture/1793776873486635033/launcher-capture.arm'
$child=Join-Path $project 'work/launcher-entry-trace-20261104-1/launcher.elf'
$seed=Join-Path $project 'work/launcher-capture/1793776873486635033/launcher-capture.bin'
function Hash([string]$Path){(Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()}
function Require-Hash([string]$Path,[string]$Expected){if((Hash $Path) -ne $Expected){throw "Hash mismatch: $Path"}}
function Plain([string]$Path){
 $node=[IO.Path]::GetFullPath($Path)
 while($node){
  if(Test-Path -LiteralPath $node){if((Get-Item -LiteralPath $node -Force).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Reparse point refused'}}
  $parent=[IO.Path]::GetDirectoryName($node);if($node -eq $parent){break};$node=$parent
 }
}
foreach($item in @($capture,$child,$seed)){Plain $item}
Require-Hash $capture $captureHash;Require-Hash $child $childHash;Require-Hash $seed $seedHash
$evidence=(& (Join-Path $PSScriptRoot 'Get-StartupUsbEvidence.ps1') | Out-String)|ConvertFrom-Json
if($evidence.status -ne 'read-only-evidence'){throw 'Verified X1060 user volume is not connected'}
if($evidence.volume_serial -ne '47799761'){throw 'Unexpected user volume identity'}
$root=$evidence.drive+'\'
$app=Join-Path $root 'HOMEBREW/launcher/app'
$backup=Join-Path $root 'HOMEBREW/launcher/app.capture-original'
$stage=Join-Path $root 'HOMEBREW/launcher/app.capture-stage'
$deviceChild=Join-Path $root 'HOMEBREW/launcher/entry-trace-app'
$trace=Join-Path $root 'HOMEBREW/data/diagnostics/launcher-capture.bin'
foreach($item in @($app,$backup,$stage,$deviceChild,$trace)){
 if(-not [IO.Path]::GetFullPath($item).StartsWith($root,[StringComparison]::OrdinalIgnoreCase)){throw 'Path outside verified user volume'}
 Plain $item
}
$plan=[ordered]@{mode=$Mode;drive=$evidence.drive;original_sha256=$originalHash;capture_sha256=$captureHash;child_sha256=$childHash;seed_sha256=$seedHash;device_program_executed=$false;firmware_flashed=$false;system_partition_written=$false}
if($Mode -eq 'Preview'){
 $plan['current_launcher_sha256']=Hash $app
 $plan['temporary_paths_present']=@(@($backup,$stage,$deviceChild,$trace)|Where-Object {Test-Path -LiteralPath $_})
 $plan|ConvertTo-Json -Depth 4;exit 0
}
$output=Join-Path $project ('work/physical-validation/launcher-capture-'+[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ'))
[IO.Directory]::CreateDirectory($output)|Out-Null
if($Mode -eq 'Install'){
 Require-Hash $app $originalHash
 foreach($item in @($backup,$stage,$deviceChild,$trace)){if(Test-Path -LiteralPath $item){throw 'Temporary path already exists; restore/review first'}}
 if([long]$evidence.free -lt 1048576){throw 'Insufficient diagnostic headroom'}
 # Require existing directories; do not silently create a fallback hierarchy.
 foreach($dir in @([IO.Path]::GetDirectoryName($trace),[IO.Path]::GetDirectoryName($app))){if(-not(Test-Path -LiteralPath $dir -PathType Container)){throw 'Expected diagnostic directory absent'}}
 $localBackup=Join-Path $output 'launcher.original.arm'
 Copy-Item -LiteralPath $app -Destination $localBackup;Require-Hash $localBackup $originalHash
 try{
  Copy-Item -LiteralPath $seed -Destination $trace;Require-Hash $trace $seedHash
  Copy-Item -LiteralPath $child -Destination $deviceChild;Require-Hash $deviceChild $childHash
  Copy-Item -LiteralPath $capture -Destination $stage;Require-Hash $stage $captureHash
  Require-Hash $app $originalHash
  Move-Item -LiteralPath $app -Destination $backup
  Move-Item -LiteralPath $stage -Destination $app
  Require-Hash $app $captureHash;Require-Hash $backup $originalHash
 }catch{
  # Recover the original executable immediately. Keep other evidence for review.
  if(Test-Path -LiteralPath $backup){Require-Hash $backup $originalHash;Copy-Item -LiteralPath $backup -Destination $app -Force;Require-Hash $app $originalHash}
  throw
 }
 $plan['installed']=$true
}else{
 Require-Hash $backup $originalHash
 $current=Hash $app
 if($current -ne $captureHash -and $current -ne $originalHash){throw 'Unexpected current executable; do not overwrite blindly'}
 # Save any record before restoration/cleanup; never silently discard it.
 if(Test-Path -LiteralPath $trace){Copy-Item -LiteralPath $trace -Destination (Join-Path $output 'launcher-capture.bin')}
 Copy-Item -LiteralPath $backup -Destination (Join-Path $output 'launcher.original.arm')
 Copy-Item -LiteralPath $backup -Destination $app -Force;Require-Hash $app $originalHash
 foreach($row in @(@($deviceChild,$childHash),@($stage,$captureHash),@($backup,$originalHash))){
  if(Test-Path -LiteralPath $row[0]){Require-Hash $row[0] $row[1];Remove-Item -LiteralPath $row[0]}
 }
 if(Test-Path -LiteralPath $trace){
  $raw=[IO.File]::ReadAllBytes($trace);$expected=[IO.File]::ReadAllBytes($seed)
  if($raw.Length -ne 4096){throw 'Restored launcher; unexpected trace length retained'}
  for($i=0;$i -lt 32;$i++){if($raw[$i] -ne $expected[$i]){throw 'Restored launcher; unexpected trace identity retained'}}
  Remove-Item -LiteralPath $trace
 }
 $plan['restored']=$true
}
$plan['current_launcher_sha256']=Hash $app
$plan['pc_evidence_directory']=$output
$json=$plan|ConvertTo-Json -Depth 4
$json|Set-Content -LiteralPath (Join-Path $output 'result.json') -Encoding utf8
$json
