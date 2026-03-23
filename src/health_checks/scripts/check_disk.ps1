# Returns JSON: [{"Drive":"C:","UsedPercent":85,"FreeGB":12.4}]
$results = Get-PSDrive -PSProvider FileSystem | Where-Object {$_.Used -gt 0} | ForEach-Object {
    $used = $_.Used
    $free = $_.Free
    $total = $used + $free
    $pct = if ($total -gt 0) { [math]::Round(($used / $total) * 100, 1) } else { 0 }
    [PSCustomObject]@{
        Drive      = $_.Name + ":"
        UsedPercent = $pct
        FreeGB     = [math]::Round($free / 1GB, 1)
        TotalGB    = [math]::Round($total / 1GB, 1)
    }
}
$results | ConvertTo-Json -Compress
