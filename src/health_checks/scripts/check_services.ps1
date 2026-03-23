# Returns JSON array of service status for critical services
param([string]$ServiceList = "wuauserv,WinRM,EventLog,MpsSvc,MdCoreSvc")
$services = $ServiceList -split ","
$results = $services | ForEach-Object {
    $svc = Get-Service -Name $_.Trim() -ErrorAction SilentlyContinue
    if ($svc) {
        [PSCustomObject]@{
            Name        = $svc.Name
            DisplayName = $svc.DisplayName
            Status      = $svc.Status.ToString()
            StartType   = $svc.StartType.ToString()
        }
    } else {
        [PSCustomObject]@{
            Name        = $_.Trim()
            DisplayName = $_.Trim()
            Status      = "NotFound"
            StartType   = "Unknown"
        }
    }
}
$results | ConvertTo-Json -Compress
