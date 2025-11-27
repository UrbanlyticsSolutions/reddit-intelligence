# PowerShell script to run workflow and push to GitHub

# 1. Run the workflow
Write-Host "Starting Reddit Intelligence Workflow..."
python run_workflow.py --comprehensive --horizon day

# 2. Find the latest output file
$latestFile = Get-ChildItem -Path "outputs" -Filter "comprehensive_reddit_data_*.json" | Sort-Object LastWriteTime -Descending | Select-Object -First 1

if ($latestFile) {
    Write-Host "Found latest output: $($latestFile.Name)"
    
    # 3. Copy to frontend/latest.json
    Copy-Item -Path $latestFile.FullName -Destination "frontend/latest.json" -Force
    Write-Host "Updated frontend/latest.json"

    # 4. Git operations
    git add frontend/latest.json
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    git commit -m "Update market intelligence data: $timestamp"
    
    Write-Host "Pushing to GitHub..."
    git push
    
    Write-Host "Done! GitHub Pages should update shortly."
} else {
    Write-Error "No output file found in outputs/"
}
