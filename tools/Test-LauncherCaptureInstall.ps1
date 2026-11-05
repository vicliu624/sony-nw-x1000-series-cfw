Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
# OFFLINE ONLY: copy the unchanged installer into a private ordinary directory.
# Replace its USB reader with a fixture, never call CIM or touch a player.
$project=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$fixture=Join-Path $project ('work/launcher-capture-installer-test/'+[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ'))
if(-not [IO.Path]::GetFullPath($fixture).StartsWith((Join-Path $project 'work')+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Fixture escaped work'}
[IO.Directory]::CreateDirectory((Join-Path $fixture 'tools'))|Out-Null
$script=Join-Path $fixture 'tools/Use-LauncherCapture.ps1'
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Use-LauncherCapture.ps1') -Destination $script
$inputs=@(
 'work/launcher-capture/1793776873486635033/launcher-capture.arm',
 'work/launcher-capture/1793776873486635033/launcher-capture.bin',
 'work/launcher-entry-trace-20261104-1/launcher.elf'
)
foreach($relative in $inputs){$destination=Join-Path $fixture $relative;[IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($destination))|Out-Null;Copy-Item -LiteralPath (Join-Path $project $relative) -Destination $destination}
$volume=Join-Path $fixture 'fake-volume'
foreach($relative in @('HOMEBREW/launcher','HOMEBREW/data/diagnostics')){[IO.Directory]::CreateDirectory((Join-Path $volume $relative))|Out-Null}
$app=Join-Path $volume 'HOMEBREW/launcher/app'
$original=Join-Path $project 'work/sdk-app-refresh/1793710385092748300/managed-launcher/launcher.elf'
Copy-Item -LiteralPath $original -Destination $app
$fake=[ordered]@{status='read-only-evidence';drive=$volume;volume_serial='47799761';free=10485760}
$fake|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $fixture 'fixture-device.json') -Encoding utf8
'Get-Content -LiteralPath (Join-Path $PSScriptRoot ''../fixture-device.json'') -Raw'|Set-Content -LiteralPath (Join-Path $fixture 'tools/Get-StartupUsbEvidence.ps1') -Encoding utf8
$shell=(Get-Process -Id $PID).Path
function Run([string]$Mode,[int]$Expected){
 $result=& $shell -NoProfile -ExecutionPolicy Bypass -File $script -Mode $Mode 2>&1
 $code=$LASTEXITCODE
 $result|Out-String|Set-Content -LiteralPath (Join-Path $fixture ($Mode+'-'+[Guid]::NewGuid().ToString('N')+'.txt')) -Encoding utf8
 if(($Expected -eq 0 -and $code -ne 0)-or($Expected -ne 0 -and $code -eq 0)){throw "Unexpected $Mode exit $code"}
}
$originalHash=(Get-FileHash -LiteralPath $original).Hash
Run Preview 0
if((Get-FileHash -LiteralPath $app).Hash -ne $originalHash){throw 'Preview changed launcher'}
Run Install 0
if((Get-FileHash -LiteralPath $app).Hash.ToLowerInvariant() -ne '1dad624e401b376b3b445344ed90ad3492e8add60f1eaf8740476d22830446a1'){throw 'Wrong installed capture'}
Run Install 1
Run Restore 0
if((Get-FileHash -LiteralPath $app).Hash -ne $originalHash){throw 'Restore mismatch'}
foreach($relative in @('HOMEBREW/launcher/app.capture-original','HOMEBREW/launcher/app.capture-stage','HOMEBREW/launcher/entry-trace-app','HOMEBREW/data/diagnostics/launcher-capture.bin')){if(Test-Path -LiteralPath (Join-Path $volume $relative)){throw 'Temporary file retained'}}
[IO.File]::WriteAllText($app,'unexpected executable')
Run Install 1
if([IO.File]::ReadAllText($app) -ne 'unexpected executable'){throw 'Mismatched original overwritten'}
$report=[ordered]@{passed=$true;scope='Unchanged installer in isolated local directory with mocked USB evidence';checks=@('preview read-only','install hashes and backup','repeat install rejected','restore exact original and cleanup','unknown original rejected');physical_device_accessed=$false;device_program_executed=$false;installer_sha256=(Get-FileHash -LiteralPath $script).Hash.ToLowerInvariant();fixture=$fixture}
$report|ConvertTo-Json -Depth 4|Set-Content -LiteralPath (Join-Path $fixture 'report.json') -Encoding utf8
$report|ConvertTo-Json -Depth 4
