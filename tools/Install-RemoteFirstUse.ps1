param([Parameter(Mandatory)][string]$PlanPath,
      [Parameter(Mandatory)][ValidatePattern('^[D-Zd-z]:$')][string]$Drive,
      [Parameter(Mandatory)][ValidatePattern('^[A-Za-z0-9_-]+$')][string]$ExpectedSerial)
$ErrorActionPreference='Stop'
Import-Module (Join-Path $PSScriptRoot 'RemoteFirstUse.psm1') -Force
$plan=Get-Content -LiteralPath $PlanPath -Raw|ConvertFrom-Json
if($plan.schema -ne 'x1000-remote-first-use-v1' -or !$plan.prepared -or $plan.installed -or $plan.target_directory -ne 'HOMEBREW/data/wireless-remote'){throw 'Unexpected first-use plan'}
$stage=[IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($PlanPath))
$destination=Join-Path ($Drive+'\') 'HOMEBREW/data/wireless-remote'
function Confirm-Walkman {
    $logical=Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='$Drive'"
    if(!$logical -or $logical.VolumeName -ne 'WALKMAN' -or $logical.FileSystem -ne 'FAT32'){throw 'Expected WALKMAN FAT32 volume not found'}
    $sonyDiskCount=0
    foreach($part in @(Get-CimAssociatedInstance -InputObject $logical -Association Win32_LogicalDiskToPartition)){
        foreach($disk in @(Get-CimAssociatedInstance -InputObject $part -Association Win32_DiskDriveToDiskPartition)){
            if($disk.PNPDeviceID -match '^USBSTOR\\DISK&VEN_SONY&PROD_WALKMAN' -and ([string]$disk.SerialNumber).Trim() -eq $ExpectedSerial){$sonyDiskCount++}
        }
    }
    if($sonyDiskCount -ne 1 -or [long]$logical.FreeSpace -lt ([long]$plan.total_bytes+16777216)){throw 'Sony identity or user-volume space check failed'}
}
Confirm-Walkman
# One attempt per frozen first-use package, including uncertain failures.
$marker=Join-Path $stage 'installation-attempt.private.json'
$stream=[IO.FileStream]::new($marker,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
try {$data=[Text.Encoding]::UTF8.GetBytes('{"attempt_started":true,"retry_requires_review":true}');$stream.Write($data,0,$data.Length);$stream.Flush($true)} finally {$stream.Dispose()}
Install-RemoteFirstUseDirectory -Source (Join-Path $stage 'files') -Destination $destination -Files $plan.files -VerifyOwnership {Confirm-Walkman}
