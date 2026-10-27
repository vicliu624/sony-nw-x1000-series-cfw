param([Parameter(Mandatory=$true)][string]$PlanPath)
$ErrorActionPreference='Stop'
$plan=Get-Content -LiteralPath $PlanPath -Raw | ConvertFrom-Json
$stage=[IO.Path]::GetFullPath($plan.stage)
$driveRoot=$plan.target_drive+'\'
$reportPath=Join-Path $stage 'install-report.json'
$backup=Join-Path $stage 'device-file-backup'
$actions=[Collections.Generic.List[object]]::new()
function Confirm-Walkman {
    $logical=Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='$($plan.target_drive)'"
    if(!$logical -or $logical.VolumeName -ne $plan.expected_label -or $logical.FileSystem -ne $plan.expected_filesystem){throw 'Expected WALKMAN FAT32 volume is not mounted'}
    $parts=Get-CimAssociatedInstance -InputObject $logical -Association Win32_LogicalDiskToPartition
    $matching=$false
    foreach($part in $parts){
        foreach($disk in @(Get-CimAssociatedInstance -InputObject $part -Association Win32_DiskDriveToDiskPartition)){
            if($disk.PNPDeviceID -match '^USBSTOR\\DISK&VEN_SONY&PROD_WALKMAN' -and ([string]$disk.SerialNumber).Trim() -eq $plan.expected_serial){$matching=$true}
        }
    }
    if(!$matching){throw 'USB disk identity differs from the selected Sony player'}
    return $logical
}
function Assert-NoReparse([string]$Path){
    $full=[IO.Path]::GetFullPath($Path)
    if(!$full.StartsWith($driveRoot,[StringComparison]::OrdinalIgnoreCase)){throw "Target outside selected drive: $full"}
    $probe=$full
    while($probe.Length -ge $driveRoot.Length){
        if(Test-Path -LiteralPath $probe){
            $item=Get-Item -LiteralPath $probe -Force
            if(($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){throw "Reparse target refused: $probe"}
        }
        if($probe.TrimEnd('\') -eq $driveRoot.TrimEnd('\')){break}
        $probe=[IO.Path]::GetDirectoryName($probe)
    }
    return $full
}
function Target-File([string]$Relative){
    if($Relative -notmatch '^HOMEBREW/apps/terminal/(app|app\.ini|files\.sha256|server-cert\.der|server-key\.der)$'){throw "Unexpected terminal install target: $Relative"}
    return Assert-NoReparse ([IO.Path]::Combine($driveRoot,$Relative.Replace('/','\')))
}
function Hash-File([string]$Path){return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()}
function Snapshot-OtherApps {
    $items=[ordered]@{}
    $appsPath=Join-Path $driveRoot 'HOMEBREW\apps'
    foreach($item in @(Get-ChildItem -LiteralPath $appsPath -File -Recurse | Sort-Object FullName)){
        $relative=$item.FullName.Substring($driveRoot.Length).Replace('\','/')
        if($relative.StartsWith('HOMEBREW/apps/terminal/')){continue}
        $null=Assert-NoReparse $item.FullName
        $items[$relative]=Hash-File $item.FullName
    }
    return $items
}
function Snapshot-FMData {
    $items=[ordered]@{}
    foreach($name in @('state-a.bin','state-b.bin','state.tmp')){
        $p=Join-Path $driveRoot ('HOMEBREW\data\fm-radio\'+$name)
        $null=Assert-NoReparse $p
        if(Test-Path -LiteralPath $p){$items[$name]=Hash-File $p}
    }
    return $items
}
function Save-Report([bool]$Success,[string]$Failure){
    [ordered]@{success=$Success;failure=$Failure;utc=[DateTime]::UtcNow.ToString('o');drive=$plan.target_drive;usb_serial=$plan.expected_serial;apps=$plan.apps;actions=@($actions.ToArray());launcher_before=$script:launcherBefore;launcher_after=$script:launcherAfter;firmware_written=$false;device_program_executed=$false;qqmusic_installed=$false;backup_directory=$backup;fm_data_before=$script:dataBefore;fm_data_after=$script:dataAfter;system_partition_added_bytes=0;terminal_installed=$true} | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $reportPath -Encoding utf8
}
$launcherBefore=$null;$launcherAfter=$null;$dataBefore=$null;$dataAfter=$null
try {
    $logical=Confirm-Walkman
    $otherBefore=Snapshot-OtherApps
    $otherBefore | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $stage 'other-apps-before.json') -Encoding utf8
    $dataBefore=Snapshot-FMData
    if([long]$logical.FreeSpace -lt ([long]$plan.total_bytes+16777216)){throw 'Insufficient free space for app files and reserve'}
    if($plan.launcher_included -or $plan.qqmusic_included -or @($plan.apps).Count -ne 1 -or $plan.apps[0].id -ne 'terminal' -or @($plan.files).Count -ne 5 -or @($plan.create_empty_dirs).Count -ne 0){throw 'Expected only the five WiFi Terminal application files'}
    $launcherPath=Join-Path $driveRoot 'HOMEBREW\launcher\app'
    if(Test-Path -LiteralPath $launcherPath){$launcherBefore=Hash-File $launcherPath}
    # Freeze/verify all sources and preserve every old file that will change before any device write.
    foreach($file in $plan.files){
        $source=[IO.Path]::GetFullPath($file.source)
        if(!$source.StartsWith($stage+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Source outside frozen staging area'}
        if((Hash-File $source) -ne $file.sha256 -or (Get-Item -LiteralPath $source).Length -ne $file.bytes){throw "Source verification failed: $($file.relative)"}
        $dest=Target-File $file.relative
        if(Test-Path -LiteralPath $dest){
            if($file.optional_keep_existing){continue}
            if((Get-Item -LiteralPath $dest).PSIsContainer){throw "Directory in place of program file: $dest"}
            if((Hash-File $dest) -ne $file.sha256){
                $save=Join-Path $backup $file.relative.Replace('/','\')
                New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($save)) -Force | Out-Null
                Copy-Item -LiteralPath $dest -Destination $save
                if((Hash-File $dest) -ne (Hash-File $save)){throw 'Backup readback failed'}
            }
        }
    }
    foreach($file in $plan.files){
        $null=Confirm-Walkman
        $dest=Target-File $file.relative
        if((Test-Path -LiteralPath $dest) -and $file.optional_keep_existing){$actions.Add([ordered]@{file=$file.relative;status='preserved-existing'});continue}
        if((Test-Path -LiteralPath $dest) -and (Hash-File $dest) -eq $file.sha256){$actions.Add([ordered]@{file=$file.relative;status='already-identical';sha256=$file.sha256});continue}
        $parent=[IO.Path]::GetDirectoryName($dest)
        $null=Assert-NoReparse $parent
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
        $temporary=$dest+'.install-'+[Guid]::NewGuid().ToString('N')+'.tmp'
        $inputStream=$null;$outputStream=$null
        try {
            $inputStream=[IO.FileStream]::new($file.source,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
            $outputStream=[IO.FileStream]::new($temporary,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None,65536,[IO.FileOptions]::WriteThrough)
            $inputStream.CopyTo($outputStream,65536)
            $outputStream.Flush($true)
        } finally {
            if($outputStream){$outputStream.Dispose()}
            if($inputStream){$inputStream.Dispose()}
        }
        if((Hash-File $temporary) -ne $file.sha256){throw "Temporary file readback failed; original target retained: $($file.relative)"}
        $null=Confirm-Walkman
        $null=Assert-NoReparse $dest
        [IO.File]::Move($temporary,$dest,$true)
        if((Hash-File $dest) -ne $file.sha256){throw "Final readback failed: $($file.relative)"}
        $actions.Add([ordered]@{file=$file.relative;status='installed';bytes=$file.bytes;sha256=$file.sha256})
        Write-Output ('Verified '+$file.relative)
    }
    $null=Confirm-Walkman
    foreach($file in $plan.files){
        if($file.optional_keep_existing){continue}
        if((Hash-File (Target-File $file.relative)) -ne $file.sha256){throw 'Final whole-install verification failed'}
    }
    if(Test-Path -LiteralPath $launcherPath){$launcherAfter=Hash-File $launcherPath}
    if($launcherAfter -ne $launcherBefore){throw 'Launcher changed unexpectedly'}
    $dataAfter=Snapshot-FMData
    if(($dataBefore | ConvertTo-Json -Compress) -ne ($dataAfter | ConvertTo-Json -Compress)){throw 'FM user data changed unexpectedly'}
    $otherAfter=Snapshot-OtherApps
    $otherAfter | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $stage 'other-apps-after.json') -Encoding utf8
    if(($otherBefore | ConvertTo-Json -Compress) -ne ($otherAfter | ConvertTo-Json -Compress)){throw 'Other applications changed unexpectedly'}
    Save-Report $true ''
    [ordered]@{success=$true;apps=@($plan.apps).Count;installed=@($actions | Where-Object {$_.status -eq 'installed'}).Count;already_identical=@($actions | Where-Object {$_.status -eq 'already-identical'}).Count;preserved_existing=@($actions | Where-Object {$_.status -eq 'preserved-existing'}).Count;launcher_unchanged=$true;report=$reportPath} | ConvertTo-Json -Compress
} catch {
    Save-Report $false $_.Exception.Message
    throw
}

