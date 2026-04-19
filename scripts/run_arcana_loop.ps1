$BASE = "https://verum-production.up.railway.app"
$REPO = "https://github.com/xzawed/ArcanaInsight"

function Wait-Status($url, $doneStatus = "done", $label = "") {
    Write-Host "  Waiting for $label..." -NoNewline
    while ($true) {
        Start-Sleep -Seconds 3
        $r = Invoke-RestMethod -Uri $url
        Write-Host "." -NoNewline
        if ($r.status -eq $doneStatus) { Write-Host " done"; return $r }
        if ($r.status -eq "error")     { Write-Host " ERROR: $($r.error)"; exit 1 }
    }
}

# Step 1 — ANALYZE
Write-Host "`n[1] Starting ANALYZE for $REPO"
$a = Invoke-RestMethod -Method POST -Uri "$BASE/v1/analyze" `
     -ContentType "application/json" `
     -Body "{`"repo_url`":`"$REPO`",`"branch`":`"main`"}"
$analysisId = $a.analysis_id
Write-Host "    analysis_id = $analysisId"

$analysis = Wait-Status "$BASE/v1/analyze/$analysisId" "done" "ANALYZE"
Write-Host "    call_sites  = $($analysis.call_sites.Count)"

# Step 2 — INFER
Write-Host "`n[2] Starting INFER"
$inf = Invoke-RestMethod -Method POST -Uri "$BASE/v1/infer/$analysisId"
$inferenceId = $inf.inference_id
Write-Host "    inference_id = $inferenceId"

$inferred = Wait-Status "$BASE/v1/infer/$inferenceId" "done" "INFER"
Write-Host "    domain     = $($inferred.domain)"
Write-Host "    confidence = $($inferred.confidence)"
Write-Host "    tone       = $($inferred.tone)"

# Step 3 — Approve all suggested sources
Write-Host "`n[3] Approving suggested sources"
foreach ($src in $inferred.suggested_sources) {
    Write-Host "    Approving: $($src.url)"
    Invoke-RestMethod -Method POST -Uri "$BASE/v1/sources/$($src.source_id)/approve" | Out-Null
}

# Step 4 — HARVEST
Write-Host "`n[4] Starting HARVEST"
$h = Invoke-RestMethod -Method POST -Uri "$BASE/v1/harvest/$inferenceId"
Write-Host "    sources_queued = $($h.sources_queued)"

Write-Host "  Waiting for HARVEST (may take 1-2 minutes)..." -NoNewline
while ($true) {
    Start-Sleep -Seconds 5
    $status = Invoke-RestMethod -Uri "$BASE/v1/harvest/$inferenceId/status"
    $done   = ($status.sources | Where-Object { $_.status -in @("done","error") }).Count
    $total  = $status.sources.Count
    Write-Host "." -NoNewline
    if ($done -ge $total -and $total -gt 0) { Write-Host " done"; break }
}

Write-Host "    total_chunks = $($status.total_chunks)"
$status.sources | ForEach-Object {
    Write-Host "    [$($_.status)] $($_.url) — $($_.chunks_count) chunks"
}

# Step 5 — Retrieve test
Write-Host "`n[5] Test retrieval: '타로 카드 의미'"
$retrieveBody = [System.Text.Encoding]::UTF8.GetBytes(
    "{`"inference_id`":`"$inferenceId`",`"query`":`"타로 카드 의미`",`"top_k`":3,`"hybrid`":true}"
)
$ret = Invoke-RestMethod -Method POST -Uri "$BASE/v1/retrieve" `
       -ContentType "application/json; charset=utf-8" `
       -Body $retrieveBody
Write-Host "    total_chunks = $($ret.total_chunks)"
$ret.results | ForEach-Object {
    Write-Host "    [score=$([math]::Round($_.score,3))] $($_.content.Substring(0, [math]::Min(80,$_.content.Length)))..."
}

Write-Host "`n=== Done. inference_id = $inferenceId ==="
