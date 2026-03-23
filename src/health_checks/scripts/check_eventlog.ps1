# Returns error/critical event count in last N hours
param([int]$HoursBack = 6)
$since = (Get-Date).AddHours(-$HoursBack)
$logs = @("System", "Application")
$results = $logs | ForEach-Object {
    $log = $_
    $count = (Get-EventLog -LogName $log -EntryType Error, Warning -After $since -ErrorAction SilentlyContinue | Measure-Object).Count
    [PSCustomObject]@{
        Log        = $log
        ErrorCount = $count
        Since      = $since.ToString("yyyy-MM-ddTHH:mm:ssZ")
    }
}
$results | ConvertTo-Json -Compress
