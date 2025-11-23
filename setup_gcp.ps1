# Google Cloud Setup Script for Reddit Intelligence
# Usage: ./setup_gcp.ps1

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "   Reddit Intelligence - Google Cloud Setup Automation" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

# 1. Check for gcloud
if (-not (Get-Command "gcloud" -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] 'gcloud' CLI is not installed or not in your PATH." -ForegroundColor Red
    Write-Host "Please install the Google Cloud SDK: https://cloud.google.com/sdk/docs/install"
    exit 1
}

# 2. Login
Write-Host "`n[1/6] Checking Authentication..." -ForegroundColor Yellow
$auth = gcloud auth list --filter=status:ACTIVE --format="value(account)"
if (-not $auth) {
    Write-Host "Not authenticated. Opening browser to login..."
    gcloud auth login
} else {
    Write-Host "Authenticated as: $auth" -ForegroundColor Green
}

# 3. Project Setup
Write-Host "`n[2/6] Project Configuration" -ForegroundColor Yellow
$projectId = Read-Host "Enter your Google Cloud Project ID (existing or new)"

# Check if project exists
$projectExists = gcloud projects list --filter="projectId:$projectId" --format="value(projectId)"
if (-not $projectExists) {
    $create = Read-Host "Project '$projectId' does not exist. Create it? (y/n)"
    if ($create -eq 'y') {
        gcloud projects create $projectId
        Write-Host "Project created." -ForegroundColor Green
    } else {
        Write-Host "Aborting." -ForegroundColor Red
        exit 1
    }
}

gcloud config set project $projectId

# 4. Enable APIs
Write-Host "`n[3/6] Enabling APIs (this may take a minute)..." -ForegroundColor Yellow
gcloud services enable run.googleapis.com artifactregistry.googleapis.com iamcredentials.googleapis.com

# 5. Create Artifact Registry
Write-Host "`n[4/6] Setting up Artifact Registry..." -ForegroundColor Yellow
$repoName = "reddit-intelligence"
$region = "us-central1"

$repoExists = gcloud artifacts repositories list --project=$projectId --location=$region --filter="name:$repoName" --format="value(name)"
if (-not $repoExists) {
    gcloud artifacts repositories create $repoName --repository-format=docker --location=$region --description="Docker repository for Reddit Intelligence"
    Write-Host "Repository '$repoName' created." -ForegroundColor Green
} else {
    Write-Host "Repository '$repoName' already exists." -ForegroundColor Green
}

# 6. Service Account
Write-Host "`n[5/6] Creating Service Account..." -ForegroundColor Yellow
$saName = "reddit-intelligence-sa"
$saEmail = "$saName@$projectId.iam.gserviceaccount.com"

$saExists = gcloud iam service-accounts list --filter="email:$saEmail" --format="value(email)"
if (-not $saExists) {
    gcloud iam service-accounts create $saName --display-name="Reddit Intelligence Service Account"
    Write-Host "Service Account created." -ForegroundColor Green
} else {
    Write-Host "Service Account already exists." -ForegroundColor Green
}

# Assign Roles
Write-Host "Assigning roles..."
gcloud projects add-iam-policy-binding $projectId --member="serviceAccount:$saEmail" --role="roles/run.admin" | Out-Null
gcloud projects add-iam-policy-binding $projectId --member="serviceAccount:$saEmail" --role="roles/iam.serviceAccountUser" | Out-Null
gcloud projects add-iam-policy-binding $projectId --member="serviceAccount:$saEmail" --role="roles/artifactregistry.writer" | Out-Null

# 7. Generate Key
Write-Host "`n[6/6] Generating Service Account Key..." -ForegroundColor Yellow
$keyPath = "$PWD\gcp_key.json"
if (Test-Path $keyPath) {
    Write-Host "Key file already exists at $keyPath" -ForegroundColor Yellow
} else {
    gcloud iam service-accounts keys create $keyPath --iam-account=$saEmail
    Write-Host "Key saved to: $keyPath" -ForegroundColor Green
}

Write-Host "`n========================================================" -ForegroundColor Cyan
Write-Host "   SETUP COMPLETE!" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "Next Steps:"
Write-Host "1. Add the content of 'gcp_key.json' to GitHub Secret: GCP_SA_KEY"
Write-Host "2. Add '$projectId' to GitHub Secret: GCP_PROJECT_ID"
Write-Host "3. Add your API keys (REDDIT_*, FMP_*, etc.) to GitHub Secrets."
