# Launch the Biosphere TUI dashboard — just type: .\run_tui.ps1
Set-Location $PSScriptRoot
& .\.venv\Scripts\Activate.ps1
$env:LOG_LEVEL = "WARNING"
$env:PYTHONPATH = "."
python -m biosphere
