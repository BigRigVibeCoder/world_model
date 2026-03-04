# Run the Biosphere demo — just double-click or type: .\run.ps1
Set-Location $PSScriptRoot
& .\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "."
python scripts\demo.py
