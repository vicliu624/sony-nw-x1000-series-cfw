[CmdletBinding()]
param(
    [string]$Distribution = 'Ubuntu-24.04',
    [string]$FirmwareReview,
    [ValidateSet('primary','secondary')][string]$SettingsLayout = 'primary',
    [switch]$RamUserVolume,
    [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if ($Distribution -match '["\r\n]' -or $repo -match '["\r\n]') {
    throw 'Unexpected quotation or newline in the distribution/repository path.'
}
foreach ($inputPath in @(
    'work/wireless-debug-venv/bin/python',
    'work/qemu-system-tool/extracted/usr/bin/qemu-system-arm',
    'work/upg-jp/verified-3.bin',
    'work/arm-block-kernel/vmlinuz-2.6.32-5-versatile'
)) {
    if (-not (Test-Path -LiteralPath (Join-Path $repo $inputPath))) {
        throw "Missing local input: $inputPath. Follow docs/QEMU.md first."
    }
}
$name = 'stock-gui-' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
$relative = 'work/' + $name
$stdout = Join-Path $repo ($relative + '.log')
$stderr = Join-Path $repo ($relative + '.stderr.log')
$distributionArgument = if ($Distribution -match '\s') { '"' + $Distribution + '"' } else { $Distribution }
$repositoryArgument = if ($repo -match '\s') { '"' + $repo + '"' } else { $repo }
$arguments = @('--distribution', $distributionArgument,
    '--cd', $repositoryArgument, '--exec',
    'work/wireless-debug-venv/bin/python', 'tools/run_stock_gui.py', '--output', $relative)
$arguments += @('--settings-layout', $SettingsLayout)
if ($RamUserVolume) { $arguments += '--ram-user-volume' }
if ($FirmwareReview) {
    $reviewPath = [IO.Path]::GetFullPath((Join-Path $repo $FirmwareReview))
    if (-not $reviewPath.StartsWith((Join-Path $repo 'work') + [IO.Path]::DirectorySeparatorChar,
            [StringComparison]::OrdinalIgnoreCase) -or
            -not (Test-Path -LiteralPath $reviewPath -PathType Leaf) -or $FirmwareReview -match '["\r\n]') {
        throw 'Firmware review must be an existing private report under work/.'
    }
    $reviewArgument = if ($FirmwareReview -match '\s') { '"' + $FirmwareReview + '"' } else { $FirmwareReview }
    $arguments += @('--firmware-review', $reviewArgument)
}
$helper = Start-Process -FilePath 'wsl.exe' -ArgumentList $arguments -WindowStyle Hidden `
    -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
$metadata = Join-Path $repo ($relative + '/server.json')
$deadline = [DateTime]::UtcNow.AddSeconds(180)
while (-not (Test-Path -LiteralPath $metadata)) {
    $helper.Refresh()
    if ($helper.HasExited) { throw "Emulator startup stopped. Inspect $stdout and $stderr." }
    if ([DateTime]::UtcNow -gt $deadline) {
        throw "Startup is still running (helper PID $($helper.Id)). Inspect $stdout."
    }
    Start-Sleep -Milliseconds 250
}
$server = Get-Content -Raw -LiteralPath $metadata | ConvertFrom-Json
$uri = [Uri]$server.url
if ($uri.Scheme -ne 'http' -or $uri.Host -ne '127.0.0.1') { throw 'Unexpected viewer address.' }
if (-not $NoBrowser) { Start-Process $uri.AbsoluteUri }
[pscustomobject]@{
    Url = $uri.AbsoluteUri
    Session = Join-Path $repo $relative
    HelperPid = $helper.Id
    PhysicalDeviceAccess = $false
    Stop = 'Use Close emulator in the viewer; closing a browser tab alone keeps the emulator running.'
}
