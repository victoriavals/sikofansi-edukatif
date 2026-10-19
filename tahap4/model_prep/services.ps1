# Jeda dan pulihkan layanan lain milik peneliti yang memakai GPU selama run model lokal (izin peneliti 2026-10-18).
# Nama layanan, URL server, dan model yang dimuat ulang dibaca dari tahap4\lokal_pribadi.env (di-ignore git;
# templat: tahap4\lokal_pribadi.example.env).
# Pemakaian (PowerShell admin):  .\services.ps1 -Action stop | start | check   (check = hanya baca status)
# Setiap aksi dicatat ke tahap4\runs\ollama_logs\services.log.
param([Parameter(Mandatory = $true)][ValidateSet("stop", "start", "check")][string]$Action)

$ErrorActionPreference = "Stop"
$log = Join-Path $PSScriptRoot "..\runs\ollama_logs\services.log"
New-Item -ItemType Directory -Force (Split-Path $log) | Out-Null
function Log($msg) { $line = "$(Get-Date -Format o) $msg"; $line; Add-Content -Path $log -Value $line -Encoding utf8 }

# Baca catatan lokal (KEY=VALUE; baris # diabaikan)
$cfgPath = Join-Path $PSScriptRoot "..\lokal_pribadi.env"
if (-not (Test-Path $cfgPath)) { throw "Tidak ada $cfgPath; salin dari lokal_pribadi.example.env lalu isi." }
$cfg = @{}
foreach ($line in Get-Content $cfgPath) {
    if ($line -match '^\s*([A-Z_]+)=(.*)$') { $cfg[$Matches[1]] = $Matches[2].Trim() }
}
$services = @($cfg["PAUSE_SERVICES"] -split "," | ForEach-Object { $_.Trim() } | Where-Object { $_ })   # urutan berhenti
$baseUrl = $cfg["PROVIDER_BASE_URL"]
$restoreModel = $cfg["PROVIDER_RESTORE_MODEL"]
if ($services.Count -eq 0) { Log "PAUSE_SERVICES kosong: tidak ada layanan yang dijeda/dipulihkan"; exit 0 }
Log ("status awal: " + ((Get-Service $services | ForEach-Object { "$($_.Name)=$($_.Status)" }) -join ", "))

if ($Action -eq "check") {
    Log "check: $($services.Count) layanan terdaftar; server=$baseUrl; model dipulihkan=$restoreModel"
    exit 0
}
if ($Action -eq "stop") {
    foreach ($s in $services) { Stop-Service -Name $s -Force; Log "berhenti: $s" }
    Start-Sleep -Seconds 3
    Log ("GPU setelah berhenti: " + (nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader))
}
else {
    [array]::Reverse($services)                                   # urutan nyala: server dulu
    foreach ($s in $services) { Start-Service -Name $s; Log "menyala: $s" }
    if ($baseUrl) {
        $ok = $false
        for ($i = 0; $i -lt 30 -and -not $ok; $i++) {
            try { Invoke-RestMethod "$baseUrl/api/version" | Out-Null; $ok = $true } catch { Start-Sleep -Seconds 1 }
        }
        if (-not $ok) { Log "PERINGATAN: server Ollama belum menjawab di $baseUrl"; exit 1 }
        if ($restoreModel) {
            # pulihkan kondisi awal: model termuat kembali (keep_alive -1)
            Invoke-RestMethod -Method Post "$baseUrl/api/generate" -ContentType "application/json" `
                -Body (@{ model = $restoreModel; keep_alive = -1 } | ConvertTo-Json) | Out-Null
        }
        Log ("ollama ps: " + ((Invoke-RestMethod "$baseUrl/api/ps").models | ForEach-Object { "$($_.name) ctx=$($_.context_length) expires=$($_.expires_at)" }))
    }
}
Log ("status akhir: " + ((Get-Service $services | ForEach-Object { "$($_.Name)=$($_.Status)" }) -join ", "))
