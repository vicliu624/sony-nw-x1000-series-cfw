Set-StrictMode -Version Latest
function Install-RemoteFirstUseDirectory {
    param([Parameter(Mandatory)][string]$Source,
          [Parameter(Mandatory)][string]$Destination,
          [Parameter(Mandatory)][object[]]$Files,
          [switch]$SharedWifi,
          [switch]$PrepareEmptyHomebrew,
          [scriptblock]$BeginAttempt = {},
          [Parameter(Mandatory)][scriptblock]$VerifyOwnership)
    $ErrorActionPreference='Stop'
    function Assert-PlainPath([string]$Path){
        $probe=[IO.Path]::GetFullPath($Path)
        while($probe){
            if(Test-Path -LiteralPath $probe){
                if((Get-Item -LiteralPath $probe -Force).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Reparse path refused'}
            }
            $next=[IO.Path]::GetDirectoryName($probe)
            if($next -eq $probe){break};$probe=$next
        }
    }
    $sourceRoot=[IO.Path]::GetFullPath($Source).TrimEnd('\','/')+[IO.Path]::DirectorySeparatorChar
    $target=[IO.Path]::GetFullPath($Destination)
    $parent=[IO.Path]::GetDirectoryName($target)
    Assert-PlainPath $sourceRoot;Assert-PlainPath $parent
    $directoriesToCreate=@()
    if(!(Test-Path -LiteralPath $parent -PathType Container)){
        if(!$PrepareEmptyHomebrew){throw 'Existing verified HOMEBREW/data directory required, or use -PrepareEmptyHomebrew for first use'}
        $homebrew=[IO.Path]::GetDirectoryName($parent)
        $volume=[IO.Path]::GetDirectoryName($homebrew)
        if([IO.Path]::GetFileName($target) -ne 'wireless-remote' -or
           [IO.Path]::GetFileName($parent) -ne 'data' -or
           [IO.Path]::GetFileName($homebrew) -ne 'HOMEBREW' -or
           !$volume -or !(Test-Path -LiteralPath $volume -PathType Container)){
            throw 'Refusing to create directories outside the first-use layout'
        }
        foreach($directory in @($homebrew,$parent)){
            if(Test-Path -LiteralPath $directory -PathType Container){continue}
            if(Test-Path -LiteralPath $directory){throw 'First-use parent is not a directory'}
            $directoriesToCreate+=$directory
        }
    }
    if(Test-Path -LiteralPath $target){throw 'First-use destination already exists; no merge or overwrite permitted'}
    $seen=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach($file in $Files){
        if($file.relative -notmatch '^(runtime/(service\.arm|owner\.arm|config\.bin)|candidate/(sd8686\.bin|helper_sd\.bin)|session\.keys|pn/pn-[0-9a-f]{64}\.dat)$' -or !$seen.Add($file.relative)){throw 'Unexpected or duplicate first-use input'}
        if($SharedWifi -and $file.relative -like 'candidate/*'){throw 'Shared Wi-Fi uses the system radio image'}
        $path=[IO.Path]::GetFullPath((Join-Path $sourceRoot $file.relative))
        Assert-PlainPath $path
        if(!$path.StartsWith($sourceRoot,[StringComparison]::OrdinalIgnoreCase)){throw 'Input escaped staging directory'}
        $probe=Get-Item -LiteralPath $path -Force
        if($probe.PSIsContainer -or ($probe.Attributes -band [IO.FileAttributes]::ReparsePoint) -or $probe.Length -ne $file.bytes -or (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $file.sha256){throw 'First-use source verification failed'}
    }
    $expectedCount=if($SharedWifi){6}else{8}
    if($Files.Count -ne $expectedCount -or @($Files|Where-Object {$_.relative -like 'pn/*'}).Count -ne 2){throw 'Complete first-use set required'}
    & $VerifyOwnership
    & $BeginAttempt
    foreach($directory in $directoriesToCreate){
        & $VerifyOwnership
        Assert-PlainPath $directory
        if(!(Test-Path -LiteralPath ([IO.Path]::GetDirectoryName($directory)) -PathType Container)){
            throw 'First-use parent disappeared during setup'
        }
        $null=[IO.Directory]::CreateDirectory($directory)
    }
    Assert-PlainPath $parent
    $temporary=Join-Path $parent ('.wireless-remote-install-'+[Guid]::NewGuid().ToString('N'))
    $committed=$false
    try {
        $null=New-Item -ItemType Directory -Path $temporary
        foreach($file in $Files){
            & $VerifyOwnership
            Assert-PlainPath $temporary;Assert-PlainPath (Join-Path $sourceRoot $file.relative)
            $path=Join-Path $temporary $file.relative
            $null=New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($path)) -Force
            $inputStream=$null;$outputStream=$null
            try {
                $inputStream=[IO.FileStream]::new((Join-Path $sourceRoot $file.relative),[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
                $outputStream=[IO.FileStream]::new($path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None,65536,[IO.FileOptions]::WriteThrough)
                $inputStream.CopyTo($outputStream);$outputStream.Flush($true)
            } finally {if($outputStream){$outputStream.Dispose()};if($inputStream){$inputStream.Dispose()}}
            if((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $file.sha256){throw 'First-use readback failed'}
        }
        & $VerifyOwnership
        Assert-PlainPath $parent
        # Directory.Move refuses an existing destination, including a race after preflight.
        [IO.Directory]::Move($temporary,$target);$committed=$true
    } finally {
        if(!$committed -and (Test-Path -LiteralPath $temporary)){
            $canClean=$true
            try { & $VerifyOwnership } catch {
                $canClean=$false
                Write-Warning 'First-use staging was left in place because WALKMAN ownership could not be reverified.'
            }
            if($canClean){
                $resolved=[IO.Path]::GetFullPath($temporary)
                if([IO.Path]::GetDirectoryName($resolved) -ne $parent -or [IO.Path]::GetFileName($resolved) -notmatch '^\.wireless-remote-install-[0-9a-f]{32}$'){throw 'Refusing cleanup outside owned staging directory'}
                Assert-PlainPath $resolved
                Remove-Item -LiteralPath $resolved -Recurse -Force
            }
        }
    }
    [pscustomobject]@{installed=$true;files=$Files.Count;overwritten=$false;firmware_written=$false;device_program_executed=$false}
}
Export-ModuleMember -Function Install-RemoteFirstUseDirectory
