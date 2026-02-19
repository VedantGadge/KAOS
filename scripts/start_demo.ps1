$env:PYTHONPATH = "$PWD"
Write-Host "🚀 Starting KAOS Control Plane..."
Write-Host "Open http://localhost:8080 in your browser once started."
python agents/control_plane/backend.py
