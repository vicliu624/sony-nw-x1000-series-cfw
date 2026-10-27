# Read-only Windows inventory. No device handles, vendor commands or volume writes.
# Run only after the user permits moving beyond this project's offline phase.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$workRoot = Join-Path $projectRoot 'work'
if (-not (Test-Path -LiteralPath $workRoot -PathType Container)) {
    throw 'Expected existing project work directory'
}
$devices = @(Get-PnpDevice -PresentOnly | Where-Object {
    $_.InstanceId -match '^USB\\VID_054C&PID_0399(?:&|\\)'
} | ForEach-Object {
    # Do not persist the serial/instance suffix.
    [pscustomobject]@{
        FriendlyName = $_.FriendlyName
        Class = $_.Class
        Status = $_.Status
        VendorId = '054C'
        ProductId = '0399'
    }
})
$disks = @(Get-CimInstance Win32_DiskDrive | Where-Object {
    $_.InterfaceType -eq 'USB' -and $_.Model -match 'SONY|WALKMAN|NW-X10'
} | ForEach-Object {
    $diskIndex = [int]$_.Index
    $modern = $null
    $modernError = $null
    try {
        $modern = Get-CimInstance -Namespace 'root/Microsoft/Windows/Storage' -ClassName MSFT_Disk -Filter "Number = $diskIndex" -ErrorAction Stop
    } catch {
        $modernError = 'Modern Windows storage metadata unavailable'
    }
    $partitions = @(Get-CimInstance Win32_DiskPartition -Filter "DiskIndex = $diskIndex" | ForEach-Object {
        [pscustomobject]@{ SizeBytes=[uint64]$_.Size; StartingOffsetBytes=[uint64]$_.StartingOffset; Type=$_.Type }
    })
    [pscustomobject]@{
        Model = $_.Model
        InterfaceType = $_.InterfaceType
        LegacyWin32SizeBytes = [uint64]$_.Size
        ModernSizeBytes = if ($null -ne $modern) { [uint64]$modern.Size } else { $null }
        LogicalSectorBytes = if ($null -ne $modern) { $modern.LogicalSectorSize } else { $null }
        PhysicalSectorBytes = if ($null -ne $modern) { $modern.PhysicalSectorSize } else { $null }
        CapacityInterfacesDisagree = if ($null -ne $modern) { [uint64]$_.Size -ne [uint64]$modern.Size } else { $null }
        ModernMetadataError = $modernError
        ExposedPartitions = $partitions
        Status = $_.Status
        Note = 'Windows exposed disk size; not internal Linux root partition capacity'
    }
})
$report = [ordered]@{
    Scope = 'Read-only Windows Plug and Play / CIM inventory; no raw device access'
    ObservedAt = [DateTimeOffset]::Now.ToString('o')
    MatchingUsbDevices = $devices
    PossibleSonyUsbDisks = $disks
    FirmwareVersionRead = $false
    InternalPartitionGeometryRead = $false
    DeviceProgramExecuted = $false
    DeviceWritten = $false
}
$json = $report | ConvertTo-Json -Depth 6
$outputPath = Join-Path $workRoot 'windows-usb-inventory.private.json'
[IO.File]::WriteAllText($outputPath, $json + [Environment]::NewLine)
$json
