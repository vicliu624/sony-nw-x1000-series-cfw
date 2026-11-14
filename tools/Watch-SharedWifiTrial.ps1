<#
.SYNOPSIS
Record X1060 IP reachability and Core2 read-only status on one timeline.
.DESCRIPTION
Use an IP verified on the player and its WLAN MAC. Record a reachable baseline
with remote Off, then enable the remote without opening Homebrew. This tool
only sends ICMP to the named IP and 'status' to the selected Core2 serial port.
It does not install firmware, provision keys or send playback commands.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ipaddress]$PlayerIp,
    [Parameter(Mandatory)][ValidatePattern('^[0-9A-Fa-f]{12}$')][string]$PlayerMac,
    [Parameter(Mandatory)][ValidatePattern('^COM[1-9][0-9]*$')][string]$Port,
    [ValidateRange(10,300)][int]$Seconds=90
)
$ErrorActionPreference='Stop'
if($PlayerIp.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork -or
   [ipaddress]::IsLoopback($PlayerIp) -or $PlayerIp.Equals([ipaddress]::Any) -or
   $PlayerIp.GetAddressBytes()[0] -ge 224){throw 'Supply the verified player IPv4 address'}
if($Port -notin [System.IO.Ports.SerialPort]::GetPortNames()){throw 'Specified serial port is not present'}
$work=Join-Path (Split-Path $PSScriptRoot -Parent) 'work'
if(!(Test-Path -LiteralPath $work -PathType Container)){throw 'Local work directory missing'}
$log=Join-Path $work ('shared-wifi-trial-'+[DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fff')+'.jsonl')
$serial=[System.IO.Ports.SerialPort]::new($Port,115200,'None',8,'One')
$ping=[System.Net.NetworkInformation.Ping]::new()
$serial.DtrEnable=$false
$serial.RtsEnable=$false
$serial.WriteTimeout=500
$buffer=''
try {
    $serial.Open()
    $serial.DiscardInBuffer()
    Write-Output "Listening on $Port. Record a baseline with remote Off. Log: $log"
    $timer=[Diagnostics.Stopwatch]::StartNew()
    while($timer.Elapsed.TotalSeconds -lt $Seconds){
        $serialProbe='Requested'
        try {$serial.Write("status`n")}
        catch [System.TimeoutException] {$serialProbe='WriteTimeout'}
        try {$probe=$ping.Send($PlayerIp,500).Status.ToString()}
        catch [System.Net.NetworkInformation.PingException] {$probe='ProbeError'}
        Start-Sleep -Milliseconds 350
        $buffer+=$serial.ReadExisting()
        $lines=$buffer -split "`n"
        $buffer=$lines[-1]
        if($buffer.Length -gt 1024){$buffer=''}
        $frames=$null
        $status=$null
        for($i=0;$i -lt $lines.Count-1;$i++){
            $line=$lines[$i].Trim()
            if($line -match '^REMOTE_RX frames=(\d+) accepted=(\d+) source=(\d+) auth=(\d+) session=(\d+) sequence=(\d+)$'){
                $frames=[ordered]@{total=[uint64]$Matches[1];accepted=[uint64]$Matches[2];wrong_source=[uint64]$Matches[3];bad_auth=[uint64]$Matches[4];bad_session=[uint64]$Matches[5];old_sequence=[uint64]$Matches[6]}
            }elseif($line -match '^REMOTE_STATUS version=([A-Za-z0-9.-]+) .* paired=([01]) player_session=([01])(?: channel=(\d+))? mac=[0-9a-fA-F]{12}$'){
                $status=[ordered]@{version=$Matches[1];paired=($Matches[2] -eq '1');player_session=($Matches[3] -eq '1');channel=$Matches[4]}
            }
        }
        $neighbors=@(Get-NetNeighbor -AddressFamily IPv4 -IPAddress $PlayerIp.IPAddressToString -ErrorAction SilentlyContinue |
                     Where-Object {$_.State -in @('Reachable','Stale','Delay','Probe') -and $_.LinkLayerAddress})
        $identity='Unconfirmed'
        if($neighbors.Count -eq 1){
            $observed=$neighbors[0].LinkLayerAddress -replace '[-:]',''
            $identity=if($observed -eq $PlayerMac){'Match'}else{'Mismatch'}
        }
        $record=[ordered]@{utc=[DateTime]::UtcNow.ToString('o');elapsed_ms=$timer.ElapsedMilliseconds;
                           icmp=$probe;player_identity=$identity;serial_probe=$serialProbe;
                           core2=$status;frames=$frames}
        $json=$record | ConvertTo-Json -Depth 4 -Compress
        Add-Content -LiteralPath $log -Value $json -Encoding utf8
        Write-Output $json
        if($identity -eq 'Mismatch'){throw 'The IP is associated with a different MAC; confirm the player address or router proxy behavior'}
        Start-Sleep -Milliseconds 450
    }
}finally{
    $serial.Dispose()
    $ping.Dispose()
}
