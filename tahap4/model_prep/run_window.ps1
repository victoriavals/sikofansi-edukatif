# Jendela run model lokal yang berdiri sendiri (tidak bergantung pada sesi agen):
#   (opsional) tunggu sampai awal jendela -StartAt tanpa menyentuh layanan
#   -> jeda layanan lain milik peneliti yang memakai GPU (daftar di tahap4\lokal_pribadi.env)
#   -> langkah di instans riset (11435): uji asap / G0 / pilot (Tahap 4) atau tahap5 (data utama, bagian B)
#   -> SELALU lepas model riset dari VRAM dan nyalakan kembali layanan (blok finally), dengan batas waktu.
# Izin peneliti 2026-10-18: simax boleh Stop/Start-Service selama run lokal.
#
# Pemakaian (PowerShell admin, dari mana saja):
#   Start-Process powershell -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File <path>\run_window.ps1' -WindowStyle Hidden
# Tahap 5 (jendela dari peneliti; waktu lokal, format yyyy-MM-ddTHH:mm:ss):
#   ... -File run_window.ps1 -Steps tahap5 -StartAt 2026-10-20T22:00:00 -WorkDeadline 2026-10-21T07:45:00 -EndAt 2026-10-21T07:50:00
#   -WorkDeadline: pengatur tidak memulai potongan dialog yang diperkirakan selesai sesudahnya (berhenti rapi);
#   -EndAt: pengaman terakhir, proses yang masih berjalan dihentikan paksa lalu layanan dipulihkan.
param([int]$MaxMinutes = 180, [string]$Steps = "smoke,g0,pilot", [string]$StartAt = "", [string]$EndAt = "",
      [string]$WorkDeadline = "")

$ErrorActionPreference = "Continue"
$T4 = Split-Path $PSScriptRoot -Parent
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$dir = Join-Path $T4 "runs\ollama_logs"
$log = Join-Path $dir "window_$stamp.log"
$py = Join-Path $T4 ".venv\Scripts\python.exe"
$bash = "C:\Program Files\Git\usr\bin\bash.exe"
$env:PYTHONUTF8 = "1"
$models = @("gemma2_9b_it", "sahabatai_9b_it")

function Log($m) { Add-Content -Path $log -Value "$(Get-Date -Format o) $m" -Encoding utf8 }
function ParseLocal([string]$s) { [datetime]::ParseExact($s, "yyyy-MM-ddTHH:mm:ss", [Globalization.CultureInfo]::InvariantCulture) }
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

$deadline = if ($EndAt) { ParseLocal $EndAt } else { (Get-Date).AddMinutes($MaxMinutes) }
$s = $Steps.Split(",")
Log "jendela run diluncurkan; langkah=$Steps; mulai=$StartAt; batas kerja=$WorkDeadline; henti paksa=$($deadline.ToString('s')); PID=$PID"
if ($s -contains "tahap5") {
    if (-not $WorkDeadline) { Log "GALAT: langkah tahap5 butuh -WorkDeadline; tidak ada yang dijalankan"; exit 1 }
    if ((ParseLocal $WorkDeadline) -gt $deadline) { Log "GALAT: -WorkDeadline sesudah -EndAt; tidak ada yang dijalankan"; exit 1 }
}
if ($StartAt) {
    $start = ParseLocal $StartAt
    if ((Get-Date) -lt $start) { Log "menunggu awal jendela $StartAt; layanan belum disentuh" }
    while ((Get-Date) -lt $start) { Start-Sleep -Seconds 20 }
}
if ((Get-Date) -ge $deadline.AddMinutes(-15)) {
    Log "jendela sudah lewat atau sisa kurang dari 15 menit; tidak ada yang dijalankan dan layanan tidak disentuh"
    exit 0
}

Log "jendela run mulai; PID=$PID"
try {
    & (Join-Path $PSScriptRoot "services.ps1") -Action stop *>&1 | Out-File -Append -Encoding utf8 $log
    if (-not (Research-Up)) {
        Log "instans riset belum hidup; menyalakan"
        # bash Git dijalankan langsung (bukan login shell), jadi alat Unix yang dipakai skrip (dirname, cygpath, sed,
        # date) harus ditambahkan ke PATH; keluaran awal skrip disimpan untuk diagnosis
        $env:PATH = "C:\Program Files\Git\usr\bin;C:\Program Files\Git\mingw64\bin;" + $env:PATH
        Start-Process -FilePath $bash -ArgumentList "model_prep/research_ollama.sh" -WorkingDirectory $T4 -WindowStyle Hidden `
            -RedirectStandardOutput (Join-Path $dir "window_${stamp}_research.out") `
            -RedirectStandardError (Join-Path $dir "window_${stamp}_research.err")
        for ($i = 0; $i -lt 60 -and -not (Research-Up); $i++) { Start-Sleep -Seconds 1 }
        if (-not (Research-Up)) { throw "instans riset gagal menyala" }
    }
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
    if ($s -contains "tahap5") {
        # data utama bagian B (izin peneliti: jendela Tahap 5); penilai berjalan terpisah, tanpa menjeda layanan
        Run-Step "tahap5_lokal" @($py, "model_prep/jalankan_tahap5_lokal.py", "hasilkan", "--deadline", $WorkDeadline)
    }
}
catch { Log "GALAT: $_" }
finally {
    # lepas model riset dari VRAM agar model milik layanan kembali dimuat penuh di GPU
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
