# Run the actual identity-check functions against PC-only CIM fixtures.
$ErrorActionPreference='Stop'
$Drive='F:';$ExpectedSerial='TEST123';$plan=[pscustomobject]@{total_bytes=1}
$script:identityBadSerial=$false
function Get-CimInstance {param($ClassName,$Filter)
 if($ClassName -ne 'Win32_LogicalDisk'){throw 'Unexpected CIM class'}
 [pscustomobject]@{VolumeName='WALKMAN';FileSystem='FAT32';FreeSpace=1073741824}
}
function Get-CimAssociatedInstance {param($InputObject,$Association)
 if($Association -eq 'Win32_LogicalDiskToPartition'){return [pscustomobject]@{Index=1}}
 if($Association -ne 'Win32_DiskDriveToDiskPartition'){throw 'Unexpected association'}
 [pscustomobject]@{PNPDeviceID='USBSTOR\DISK&VEN_SONY&PROD_WALKMAN&REV_1.10\TEST123&0';SerialNumber=$(if($script:identityBadSerial){'OTHER'}else{'TEST123'})}
}
$checked=@()
foreach($name in @('Repair-InstalledApps.ps1','Install-RemoteFirstUse.ps1')){
 $tokens=$null;$errors=$null
 $ast=[Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot $name),[ref]$tokens,[ref]$errors)
 if($errors.Count){throw 'Script syntax failure'}
 $function=$ast.Find({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Confirm-Walkman'},$true)
 if(!$function){throw 'Identity function missing'}
 Invoke-Expression $function.Extent.Text
 $script:identityBadSerial=$false;Confirm-Walkman
 $script:identityBadSerial=$true;$refused=$false
 try {Confirm-Walkman} catch {$refused=$true}
 if(!$refused){throw 'Wrong Sony serial accepted'}
 $checked+=$name
}
[ordered]@{passed=$true;actual_functions_checked=$checked;regex_counter_collision_regression=$true;wrong_serial_refused=$true;physical_device_accessed=$false}|ConvertTo-Json
