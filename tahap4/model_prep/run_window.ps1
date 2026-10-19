# Jendela run model lokal yang berdiri sendiri (tidak bergantung pada sesi agen):
#   jeda layanan lain milik peneliti yang memakai GPU (daftar di tahap4\lokal_pribadi.env)
#   -> uji asap + G0 + pilot di instans riset (11435)
#   -> SELALU lepas model riset dari VRAM dan nyalakan kembali layanan (blok finally), dengan batas waktu.
# Izin peneliti 2026-10-18: simax boleh Stop/Start-Service selama run lokal.
#
# Pemakaian (PowerShell admin, dari mana saja):
#   Start-Process powershell -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File <path>\run_window.ps1' -WindowStyle Hidden
param([int]$MaxMinutes = 180, [string]$Steps = "smoke,g0,pilot")

$ErrorActionPreference = "Continue"
$T4 = Split-Path $PSScriptRoot -Parent
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$dir = Join-Path $T4 "runs\ollama_logs"
$log = Join-Path $dir "window_$stamp.log"
$py = Join-Path $T4 ".venv\Scripts\python.exe"
$bash = "C:\Program Files\Git\usr\bin\bash.exe"
$deadline = (Get-Date).AddMinutes($MaxMinutes)
$env:PYTHONUTF8 = "1"
$models = @("gemma2_9b_it", "sahabatai_9b_it")

function Log($m) { Add-Content -Path $log -Value "$(Get-Date -Format o) $m" -Encoding utf8 }
function Research-Up {
    try { Invoke-RestMethod http://127.0.0.1:11435/api/version -TimeoutSec 3 | Out-Null; return $true } catch { return $false }
}
function Run-Step([string]$name, [string[]]$cmd) {
    $remaining = [int]($deadline - (Get-Date)).TotalMilliseconds
    if ($remaining -le 0) { Log "lewati ${name}: batas waktu jendela habis"; return }
    $out = Join-Path $dir "window_${stamp}_$name.out"
    Log "mulai ${name}: $($cmd -join ' ')"
    $p = Start-Process -FilePath $cmd[0] -ArgumentList $cmd[1..($cmd.Length - 1)] -WorkingDirectory $T4 `
        -RedirectStandardOutput $out -RedirectStandardError "$out.err" -NoNewWindow -PassThru
    $null = $p.Handle   # tanpa ini ExitCode bisa kosong setelah WaitForExit(timeout)
    if (-not $p.WaitForExit($remaining)) {
        Log "BATAS WAKTU: hentikan $name (PID $($p.Id)); sisa pekerjaan bisa dilanjutkan (resume) di jendela berikut"
        taskkill /PID $p.Id /T /F | Out-Null
        return
    }
    Log "selesai ${name}: exit=$($p.ExitCode)"
}

Log "jendela run mulai; langkah=$Steps; batas=$MaxMinutes menit; PID=$PID"
try {
    & (Join-Path $PSScriptRoot "services.ps1") -Action stop *>&1 | Out-File -Append -Encoding utf8 $log
    if (-not (Research-Up)) {
        Log "instans riset belum hidup; menyalakan"
        Start-Process -FilePath $bash -ArgumentList "model_prep/research_ollama.sh" -WorkingDirectory $T4 -WindowStyle Hidden
        for ($i = 0; $i -lt 60 -and -not (Research-Up); $i++) { Start-Sleep -Seconds 1 }
        if (-not (Research-Up)) { throw "instans riset gagal menyala" }
    }
    $s = $Steps.Split(",")
    if ($s -contains "smoke") {
        foreach ($m in $models) {
            Run-Step "smoke_$m" @($py, "-I", "model_prep/smoke_test.py", $m, "reports/smoke/smoke_${m}_kvf16_numgpu36.json",
                "http://127.0.0.1:11435", "36")
        }
    }
    if ($s -contains "g0") { Run-Step "g0" (@($py, "-m", "src.run_g0", "--models") + $models) }
    if ($s -contains "pilot") {
        Run-Step "pilot" (@($py, "-m", "src.run_dialogs", "--models") + $models + @("--items", "A04", "B01", "D02", "E02", "A08", "--reps", "1"))
    }
}
catch { Log "GALAT: $_" }
finally {
    # lepas model riset dari VRAM agar gemma3:4b milik layanan kembali dimuat penuh di GPU
    try {
        foreach ($m in (Invoke-RestMethod http://127.0.0.1:11435/api/ps -TimeoutSec 5).models) {
            Invoke-RestMethod -Method Post http://127.0.0.1:11435/api/generate -ContentType "application/json" `
                -Body (@{ model = $m.name; keep_alive = 0 } | ConvertTo-Json) | Out-Null
            Log "lepas dari VRAM: $($m.name)"
        }
    }
    catch { Log "gagal melepas model riset: $_" }
    Start-Sleep -Seconds 3
    & (Join-Path $PSScriptRoot "services.ps1") -Action start *>&1 | Out-File -Append -Encoding utf8 $log
    Log "jendela run selesai"
}
