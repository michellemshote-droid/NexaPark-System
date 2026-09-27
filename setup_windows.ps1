# NexaPark Windows setup (PowerShell)
$ErrorActionPreference = "Stop"

Write-Host "Setting up NexaPark..."

if (Get-Command python -ErrorAction SilentlyContinue) {
    $python = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $python = "py"
} else {
    throw "Python was not found. Install Python 3.10+ and try again."
}

& $python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt

Write-Host ""
Write-Host "NexaPark dependencies are installed."
Write-Host "Activate the environment with: .\.venv\Scripts\Activate.ps1"
Write-Host "Then create an admin account with: flask --app app.py create-admin"
Write-Host "Then start the application with: python app.py"
