param([ValidatePattern('^[A-Za-z0-9_-]+$')][string]$ExpectedSerial='10FA7C05062586')
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
# PC-only readback. No device command, program execution, repair or file write.
$selected=@()
foreach($logical in @(Get-CimInstance Win32_LogicalDisk)){
    if($logical.VolumeName -ne 'WALKMAN' -or $logical.FileSystem -ne 'FAT32'){continue}
    foreach($part in @(Get-CimAssociatedInstance -InputObject $logical -Association Win32_LogicalDiskToPartition)){
        foreach($disk in @(Get-CimAssociatedInstance -InputObject $part -Association Win32_DiskDriveToDiskPartition)){
            if($disk.PNPDeviceID -match '^USBSTOR\\DISK&VEN_SONY&PROD_WALKMAN' -and ([string]$disk.SerialNumber).Trim() -eq $ExpectedSerial){
                $selected+=@{logical=$logical;disk=$disk}
            }
        }
    }
}
if($selected.Count -eq 0){
    [ordered]@{status='expected-device-not-connected';device_written=$false;device_program_executed=$false}|ConvertTo-Json
    exit 0
}
if($selected.Count -ne 1){throw 'Expected exactly one verified Sony volume'}
$volume=$selected[0].logical
$root=$volume.DeviceID+'\'
function Assert-PlainDevicePath([string]$Path){
    $probe=[IO.Path]::GetFullPath($Path)
    while($probe){
        if(Test-Path -LiteralPath $probe){
            if((Get-Item -LiteralPath $probe -Force).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Reparse path refused'}
        }
        $parent=[IO.Path]::GetDirectoryName($probe)
        if($parent -eq $probe){break};$probe=$parent
    }
}
$files=@()
foreach($name in @('NW_WM_FW.UPG','HOMEBREW/launcher/app')){
    $path=Join-Path $root $name
    Assert-PlainDevicePath $path
    if(Test-Path -LiteralPath $path -PathType Leaf){
        $item=Get-Item -LiteralPath $path -Force
        $files+=[ordered]@{relative=$name;exists=$true;bytes=$item.Length;sha256=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()}
    }else{$files+=[ordered]@{relative=$name;exists=$false}}
}
$report=[ordered]@{status='read-only-evidence';drive=$volume.DeviceID;volume_serial=$volume.VolumeSerialNumber;size=$volume.Size;free=$volume.FreeSpace;files=$files;installed_system_hash_readback=$false;device_written=$false;device_program_executed=$false;limits='A leftover UPG is transfer evidence, not proof of the installed root filesystem. No account, pairing or ROM data read.'}
$project=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$output=Join-Path $project ('work/physical-validation/usb-startup-'+[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ'))
[IO.Directory]::CreateDirectory($output)|Out-Null
$json=$report|ConvertTo-Json -Depth 6
$json|Set-Content -LiteralPath (Join-Path $output 'report.json') -Encoding utf8
$json
