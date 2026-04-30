# Quick CORS Fix Script
# Run this if you're experiencing CORS errors after deployment
# Usage: .\deployment\fix-cors.ps1 -StackName resume-formatter-demo -Region ap-south-1

param (
    [string]$Region = "ap-south-1",
    [string]$StackName = "resume-formatter-demo"
)

$ErrorActionPreference = "Stop"

Write-Host "`n=== CORS Configuration Fix ===" -ForegroundColor Cyan
Write-Host "Stack: $StackName" -ForegroundColor Yellow
Write-Host "Region: $Region`n" -ForegroundColor Yellow

# Get Stack Outputs
Write-Host "Fetching stack information..." -ForegroundColor Cyan
$Outputs = aws cloudformation describe-stacks --stack-name $StackName --region $Region --query "Stacks[0].Outputs" --output json | ConvertFrom-Json

$FrontendUrl = ($Outputs | Where-Object { $_.OutputKey -eq "FrontendUrl" }).OutputValue
$ApiUrl = ($Outputs | Where-Object { $_.OutputKey -eq "ApiUrl" }).OutputValue
$StorageBucket = ($Outputs | Where-Object { $_.OutputKey -eq "StorageBucketName" }).OutputValue
$FrontendBucket = ($Outputs | Where-Object { $_.OutputKey -eq "FrontendBucketName" }).OutputValue

Write-Host "Frontend URL: $FrontendUrl" -ForegroundColor Gray
Write-Host "API URL: $ApiUrl" -ForegroundColor Gray

# Fix 1: Update S3 CORS Configuration
Write-Host "`n1. Updating S3 CORS configuration..." -ForegroundColor Cyan

$corsPolicyStorage = @"
{
  "CORSRules": [
    {
      "AllowedOrigins": ["*"],
      "AllowedMethods": ["GET", "POST", "PUT", "DELETE", "HEAD"],
      "AllowedHeaders": ["*"],
      "ExposeHeaders": ["ETag"],
      "MaxAgeSeconds": 3600
    }
  ]
}
"@

$corsPolicyFrontend = @"
{
  "CORSRules": [
    {
      "AllowedOrigins": ["*"],
      "AllowedMethods": ["GET", "HEAD"],
      "AllowedHeaders": ["*"],
      "MaxAgeSeconds": 3600
    }
  ]
}
"@

# Write CORS policies to temp files
$corsPolicyStorage | Out-File -FilePath "cors-storage.json" -Encoding UTF8
$corsPolicyFrontend | Out-File -FilePath "cors-frontend.json" -Encoding UTF8

try {
    Write-Host "  Applying CORS to storage bucket: $StorageBucket" -ForegroundColor Gray
    aws s3api put-bucket-cors --bucket $StorageBucket --cors-configuration file://cors-storage.json --region $Region
    Write-Host "  ✓ Storage bucket CORS updated" -ForegroundColor Green
} catch {
    Write-Host "  ⚠ Could not update storage bucket CORS" -ForegroundColor Yellow
}

try {
    Write-Host "  Applying CORS to frontend bucket: $FrontendBucket" -ForegroundColor Gray
    aws s3api put-bucket-cors --bucket $FrontendBucket --cors-configuration file://cors-frontend.json --region $Region
    Write-Host "  ✓ Frontend bucket CORS updated" -ForegroundColor Green
} catch {
    Write-Host "  ⚠ Could not update frontend bucket CORS" -ForegroundColor Yellow
}

# Clean up temp files
Remove-Item "cors-storage.json" -ErrorAction SilentlyContinue
Remove-Item "cors-frontend.json" -ErrorAction SilentlyContinue

# Fix 2: Verify App Runner CORS Environment Variable
Write-Host "`n2. Checking App Runner CORS configuration..." -ForegroundColor Cyan

$serviceName = "$StackName-api"
$services = aws apprunner list-services --region $Region --output json | ConvertFrom-Json
$service = $services.ServiceSummaryList | Where-Object { $_.ServiceName -eq $serviceName }

if ($service) {
    $serviceDetails = aws apprunner describe-service --service-arn $service.ServiceArn --region $Region --output json | ConvertFrom-Json
    $envVars = $serviceDetails.Service.SourceConfiguration.ImageRepository.ImageConfiguration.RuntimeEnvironmentVariables
    
    $corsOriginsVar = $envVars | Where-Object { $_.Name -eq "CORS_ORIGINS" }
    
    if ($corsOriginsVar) {
        Write-Host "  Current CORS_ORIGINS: $($corsOriginsVar.Value)" -ForegroundColor Gray
        
        # Check if it matches frontend URL
        $expectedCors = "$FrontendUrl,$($FrontendUrl -replace 'http://', 'https://')"
        if ($corsOriginsVar.Value -ne $expectedCors) {
            Write-Host "  ⚠ CORS_ORIGINS may need updating" -ForegroundColor Yellow
            Write-Host "    Expected: $expectedCors" -ForegroundColor Yellow
            Write-Host "    To fix: Redeploy the stack with correct CORS_ORIGINS" -ForegroundColor Yellow
        } else {
            Write-Host "  ✓ CORS_ORIGINS is correctly configured" -ForegroundColor Green
        }
    } else {
        Write-Host "  ✗ CORS_ORIGINS environment variable not set!" -ForegroundColor Red
        Write-Host "    This must be set in CloudFormation template" -ForegroundColor Yellow
    }
} else {
    Write-Host "  ✗ App Runner service not found" -ForegroundColor Red
}

# Fix 3: Test CORS
Write-Host "`n3. Testing CORS configuration..." -ForegroundColor Cyan

try {
    Write-Host "  Testing OPTIONS preflight request..." -ForegroundColor Gray
    $response = Invoke-WebRequest -Uri "https://$ApiUrl/health" -Method Options -Headers @{
        "Origin" = $FrontendUrl
        "Access-Control-Request-Method" = "GET"
    } -ErrorAction Stop
    
    $allowOrigin = $response.Headers["Access-Control-Allow-Origin"]
    $allowMethods = $response.Headers["Access-Control-Allow-Methods"]
    
    if ($allowOrigin) {
        Write-Host "  ✓ CORS preflight successful" -ForegroundColor Green
        Write-Host "    Allow-Origin: $allowOrigin" -ForegroundColor Gray
        Write-Host "    Allow-Methods: $allowMethods" -ForegroundColor Gray
    } else {
        Write-Host "  ✗ CORS headers not present in response" -ForegroundColor Red
    }
} catch {
    Write-Host "  ⚠ Could not test CORS (service may be unavailable)" -ForegroundColor Yellow
}

# Summary
Write-Host "`n=== Summary ===" -ForegroundColor Cyan
Write-Host @"

CORS Configuration Applied:
1. S3 buckets updated with CORS rules
2. App Runner CORS_ORIGINS checked

Next Steps:
1. Wait 30 seconds for changes to propagate
2. Clear your browser cache (Ctrl+Shift+Delete)
3. Open browser DevTools (F12) > Network tab
4. Reload your frontend: $FrontendUrl
5. Look for API requests and check response headers

If CORS errors persist:
- Check that frontend is using the correct API URL
- Verify App Runner CORS_ORIGINS includes your frontend URL
- Run diagnostics: .\deployment\diagnose-deployment.ps1

Browser Test:
Open DevTools Console and run:
  fetch('https://$ApiUrl/health')
    .then(r => r.json())
    .then(d => console.log('API Response:', d))
    .catch(e => console.error('CORS Error:', e))

"@ -ForegroundColor Gray

Write-Host "Done!`n" -ForegroundColor Green
