$ErrorActionPreference='Stop'
Import-Module (Join-Path $PSScriptRoot 'RemoteFirstUse.psm1') -Force
$project=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$root=Join-Path $project ('work/remote-first-use-tests/'+[Guid]::NewGuid().ToString('N'))
$null=New-Item -ItemType Directory -Path $root
try {
    $source=Join-Path $root 'source';$null=New-Item -ItemType Directory -Path $source
    $names=@('runtime/service.arm','runtime/owner.arm','runtime/config.bin','candidate/sd8686.bin','candidate/helper_sd.bin','session.keys',('pn/pn-'+('a'*64)+'.dat'),('pn/pn-'+('b'*64)+'.dat'))
    $files=foreach($name in $names){
        $path=Join-Path $source $name;$null=New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($path)) -Force
        [IO.File]::WriteAllText($path,'Synthetic fixture '+$name)
        [pscustomobject]@{relative=$name;bytes=(Get-Item $path).Length;sha256=(Get-FileHash $path -Algorithm SHA256).Hash}
    }
    $target=Join-Path $root 'installed'
    $attempt=Join-Path $root 'attempt'
    $beginAttempt = {[IO.File]::WriteAllText($attempt,'started')}
    $missingParent=Join-Path $root 'HOMEBREW/data/wireless-remote'
    $rejected=$false
    try {Install-RemoteFirstUseDirectory -Source $source -Destination $missingParent -Files $files -VerifyOwnership {} -BeginAttempt $beginAttempt|Out-Null} catch {$rejected=$true}
    if(!$rejected -or (Test-Path -LiteralPath $attempt)){throw 'Missing parent consumed the installation attempt'}
    $result=Install-RemoteFirstUseDirectory -Source $source -Destination $target -Files $files -VerifyOwnership {} -BeginAttempt $beginAttempt
    if(!(Test-Path -LiteralPath $attempt)){throw 'Installation proceeded without an attempt record'}
    if(!$result.installed){throw 'Initial installation failed'}
    $rejected=$false
    try {Install-RemoteFirstUseDirectory -Source $source -Destination $target -Files $files -VerifyOwnership {}|Out-Null} catch {$rejected=$true}
    if(!$rejected){throw 'Duplicate install accepted'}
    foreach($f in $files){if((Get-FileHash (Join-Path $target $f.relative) -Algorithm SHA256).Hash -ne $f.sha256){throw 'Existing state changed'}}
    $script:calls=0;$failed=Join-Path $root 'failed';$rejected=$false
    try {Install-RemoteFirstUseDirectory -Source $source -Destination $failed -Files $files -VerifyOwnership {$script:calls++;if($script:calls -eq 4){throw 'Simulated ownership loss'}}|Out-Null} catch {$rejected=$true}
    if(!$rejected -or (Test-Path $failed) -or @(Get-ChildItem $root -Force -Filter '.wireless-remote-install-*').Count){throw 'Failed stage not cleaned'}
    $otherVolume=Join-Path $root 'lost-owner'
    $null=New-Item -ItemType Directory -Path $otherVolume
    $script:calls=0;$rejected=$false
    try {
        Install-RemoteFirstUseDirectory -Source $source -Destination (Join-Path $otherVolume 'target') -Files $files -VerifyOwnership {
            $script:calls++
            if($script:calls -ge 4){throw 'Simulated persistent ownership loss'}
        } | Out-Null
    } catch {$rejected=$true}
    if(!$rejected -or @(Get-ChildItem $otherVolume -Force -Filter '.wireless-remote-install-*').Count -ne 1){
        throw 'Cleanup modified a volume whose ownership could not be verified'
    }
    $script:calls=0;$race=Join-Path $root 'race';$rejected=$false
    try {Install-RemoteFirstUseDirectory -Source $source -Destination $race -Files $files -VerifyOwnership {$script:calls++;if($script:calls -eq 10){$null=New-Item -ItemType Directory $race;[IO.File]::WriteAllText((Join-Path $race 'existing'),'keep')}}|Out-Null} catch {$rejected=$true}
    if(!$rejected -or [IO.File]::ReadAllText((Join-Path $race 'existing')) -ne 'keep'){throw 'Commit race overwrote existing data'}
    $shared=@($files | Where-Object {$_.relative -notlike 'candidate/*'})
    $result=Install-RemoteFirstUseDirectory -Source $source -Destination $missingParent -Files $shared -SharedWifi -PrepareEmptyHomebrew -VerifyOwnership {}
    if(!$result.installed -or !(Test-Path -LiteralPath (Join-Path $missingParent 'runtime/owner.arm'))){throw 'Empty user volume setup failed'}
    $sharedTarget=Join-Path $root 'shared'
    $result=Install-RemoteFirstUseDirectory -Source $source -Destination $sharedTarget -Files $shared -SharedWifi -VerifyOwnership {}
    if(!$result.installed -or (Test-Path -LiteralPath (Join-Path $sharedTarget 'candidate'))){throw 'Shared Wi-Fi layout incorrect'}
    $rejected=$false
    try {Install-RemoteFirstUseDirectory -Source $source -Destination (Join-Path $root 'mixed') -Files $files -SharedWifi -VerifyOwnership {}|Out-Null} catch {$rejected=$true}
    if(!$rejected){throw 'Shared installer accepted user radio images'}
    [ordered]@{passed=$true;duplicate_refused=$true;ownership_loss_cleaned=$true;commit_race_preserved=$true;shared_layout_passed=$true;physical_device_accessed=$false}|ConvertTo-Json
} finally {
    $resolved=[IO.Path]::GetFullPath($root)
    if(!$resolved.StartsWith((Join-Path $project 'work/remote-first-use-tests/'),[StringComparison]::OrdinalIgnoreCase)){throw 'Test cleanup escaped workspace'}
    Remove-Item -LiteralPath $resolved -Recurse -Force
}
