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
    $result=Install-RemoteFirstUseDirectory -Source $source -Destination $target -Files $files -VerifyOwnership {}
    if(!$result.installed){throw 'Initial installation failed'}
    $rejected=$false
    try {Install-RemoteFirstUseDirectory -Source $source -Destination $target -Files $files -VerifyOwnership {}|Out-Null} catch {$rejected=$true}
    if(!$rejected){throw 'Duplicate install accepted'}
    foreach($f in $files){if((Get-FileHash (Join-Path $target $f.relative) -Algorithm SHA256).Hash -ne $f.sha256){throw 'Existing state changed'}}
    $script:calls=0;$failed=Join-Path $root 'failed';$rejected=$false
    try {Install-RemoteFirstUseDirectory -Source $source -Destination $failed -Files $files -VerifyOwnership {$script:calls++;if($script:calls -eq 4){throw 'Simulated ownership loss'}}|Out-Null} catch {$rejected=$true}
    if(!$rejected -or (Test-Path $failed) -or @(Get-ChildItem $root -Force -Filter '.wireless-remote-install-*').Count){throw 'Failed stage not cleaned'}
    $script:calls=0;$race=Join-Path $root 'race';$rejected=$false
    try {Install-RemoteFirstUseDirectory -Source $source -Destination $race -Files $files -VerifyOwnership {$script:calls++;if($script:calls -eq 10){$null=New-Item -ItemType Directory $race;[IO.File]::WriteAllText((Join-Path $race 'existing'),'keep')}}|Out-Null} catch {$rejected=$true}
    if(!$rejected -or [IO.File]::ReadAllText((Join-Path $race 'existing')) -ne 'keep'){throw 'Commit race overwrote existing data'}
    [ordered]@{passed=$true;duplicate_refused=$true;ownership_loss_cleaned=$true;commit_race_preserved=$true;physical_device_accessed=$false}|ConvertTo-Json
} finally {
    $resolved=[IO.Path]::GetFullPath($root)
    if(!$resolved.StartsWith((Join-Path $project 'work/remote-first-use-tests/'),[StringComparison]::OrdinalIgnoreCase)){throw 'Test cleanup escaped workspace'}
    Remove-Item -LiteralPath $resolved -Recurse -Force
}
