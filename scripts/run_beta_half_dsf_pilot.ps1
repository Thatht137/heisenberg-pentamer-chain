$ErrorActionPreference = "Stop"

$alphas = @("-0.50", "-0.05", "0.14", "0.23", "0.33")
$beta = "0.5"
$nUnits = 8
$totalSites = 5 * $nUnits
$outputTag = "L40_t15"

$env:PENTAMER_N_UNITS = "$nUnits"
$env:PENTAMER_BETA = $beta
$env:PENTAMER_TSTEP = "0.05"
$env:PENTAMER_N_STEPS = "300"
$env:PENTAMER_DMRG_MAXDIM = "160"
$env:PENTAMER_TEBD_MAXDIM = "160"
$env:PENTAMER_DMRG_CUTOFF = "1e-9"
$env:PENTAMER_TEBD_CUTOFF = "1e-8"
$env:PENTAMER_NSWEEPS = "12"
$env:PENTAMER_Q_POINTS = "81"
$env:PENTAMER_OMEGA_POINTS = "181"
$env:PENTAMER_OMEGA_MAX = "3.0"
$env:PENTAMER_SPACE_WINDOW = "18"
$env:PENTAMER_OUTPUT_TAG = $outputTag

foreach ($alphaText in $alphas) {
    $alpha = [double]::Parse(
        $alphaText,
        [System.Globalization.CultureInfo]::InvariantCulture
    )
    $alphaLabel = $alpha.ToString(
        "G",
        [System.Globalization.CultureInfo]::InvariantCulture
    )
    $env:PENTAMER_ALPHA = $alphaLabel

    $tebdName =
        "NDSF_pentamer_alpha=$alphaLabel" +
        "_beta=$beta" +
        "_L=$totalSites" +
        "_$outputTag.jld2"
    $tebdFile = Join-Path -Path "data" -ChildPath $tebdName

    $spectrumName =
        "Sqw_tebd_pentamer_alpha=$alphaLabel" +
        "_beta=$beta" +
        "_$outputTag.jld2"
    $spectrumFile = Join-Path -Path "data" -ChildPath $spectrumName

    Write-Host "`n=== alpha=$alphaLabel, beta=$beta ==="
    if (-not (Test-Path -LiteralPath $tebdFile)) {
        julia --project=. scripts/05_tebd_pentamer_server.jl
        if ($LASTEXITCODE -ne 0) {
            throw "TEBD failed: alpha=$alphaLabel"
        }
    } else {
        Write-Host "Skip existing TEBD: $tebdFile"
    }

    if (-not (Test-Path -LiteralPath $spectrumFile)) {
        julia --project=. scripts/06_ft_tebd_pentamer_mapped_server.jl
        if ($LASTEXITCODE -ne 0) {
            throw "Fourier transform failed: alpha=$alphaLabel"
        }
    } else {
        Write-Host "Skip existing DSF: $spectrumFile"
    }
}

Write-Host "`nFive-point pilot DSF scan completed."
