# Diagnose AWS Deployment Issues
# Usage: .\deployment\diagnose-deployment.ps1 -StackName resume-formatter-demo -Region ap-south-1

param (
    [string]$Region = "ap-south-1",
    [string]$StackName = "resume-formatter-demo"
)

$ErrorActionPreference = "Continue"

Write-Host "`n=== AWS Deployment Diagnostics ===" -ForegroundColor Cyan
Write-Host "Stack: $StackName" -ForegroundColor Yellow
Write-Host "Region: $Region`n" -ForegroundColor Yellow

# Get Stack Outputs
Write-Host "Fetching Stack Information..." -ForegroundColor Cyan
try {
    $Stack = aws cloudformation describe-stacks --stack-name $StackName --region $Region --output json | ConvertFrom-Json
    $StackStatus = $Stack.Stacks[0].StackStatus
    $Outputs = $Stack.Stacks[0].Outputs
    
    Write-Host "Stack Status: $StackStatus" -ForegroundColor $(if ($StackStatus -like "*COMPLETE*") { "Green" } else { "Yellow" })
    
    $ApiUrl = ($Outputs | Where-Object { $_.OutputKey -eq "ApiUrl" }).OutputValue
    $FrontendUrl = ($Outputs | Where-Object { $_.OutputKey -eq "FrontendUrl" }).OutputValue
    $StorageBucket = ($Outputs | Where-Object { $_.OutputKey -eq "StorageBucketName" }).OutputValue
    $FrontendBucket = ($Outputs | Where-Object { $_.OutputKey -eq "FrontendBucketName" }).OutputValue
    
    Write-Host "`nStack Outputs:" -ForegroundColor Cyan
    Write-Host "  Frontend URL: $FrontendUrl" -ForegroundColor Gray
    Write-Host "  API URL: $ApiUrl" -ForegroundColor Gray
    Write-Host "  Storage Bucket: $StorageBucket" -ForegroundColor Gray
    Write-Host "  Frontend Bucket: $FrontendBucket" -ForegroundColor Gray
} catch {
    Write-Host "Error: Stack not found or cannot be accessed" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Yellow
    exit 1
}

# Check 1: API Health Endpoint
Write-Host "`n=== Checking API Health ===" -ForegroundColor Cyan
try {
    $healthUrl = "https://$ApiUrl/health"
    Write-Host "Testing: $healthUrl" -ForegroundColor Gray
    
    $response = Invoke-RestMethod -Uri $healthUrl -Method Get -TimeoutSec 15 -ErrorAction Stop
    Write-Host "✓ API is responding" -ForegroundColor Green
    Write-Host "  Status: $($response.status)" -ForegroundColor Gray
    Write-Host "  Cloud Mode: $($response.cloud_mode)" -ForegroundColor Gray
} catch {
    Write-Host "✗ API health check failed" -ForegroundColor Red
    Write-Host "  Error: $($_.Exception.Message)" -ForegroundColor Yellow
    Write-Host "  This could indicate App Runner is still starting or has errors" -ForegroundColor Yellow
}

# Check 2: API Docs Endpoint
Write-Host "`n=== Checking API Documentation ===" -ForegroundColor Cyan
try {
    $docsUrl = "https://$ApiUrl/docs"
    Write-Host "Testing: $docsUrl" -ForegroundColor Gray
    
    $response = Invoke-WebRequest -Uri $docsUrl -Method Get -TimeoutSec 10 -ErrorAction Stop
    if ($response.StatusCode -eq 200) {
        Write-Host "✓ API docs are accessible" -ForegroundColor Green
    }
} catch {
    Write-Host "✗ API docs check failed" -ForegroundColor Red
    Write-Host "  Error: $($_.Exception.Message)" -ForegroundColor Yellow
}

# Check 3: CORS Configuration
Write-Host "`n=== Checking CORS Configuration ===" -ForegroundColor Cyan
try {
    $response = Invoke-WebRequest -Uri "https://$ApiUrl/health" -Method Options -Headers @{
        "Origin" = $FrontendUrl
        "Access-Control-Request-Method" = "GET"
    } -ErrorAction Stop
    
    $corsHeader = $response.Headers["Access-Control-Allow-Origin"]
    if ($corsHeader) {
        Write-Host "✓ CORS headers present" -ForegroundColor Green
        Write-Host "  Allowed Origins: $corsHeader" -ForegroundColor Gray
    } else {
        Write-Host "✗ CORS headers missing" -ForegroundColor Red
        Write-Host "  This will cause frontend API calls to fail" -ForegroundColor Yellow
    }
} catch {
    Write-Host "⚠ Could not test CORS (service may be down)" -ForegroundColor Yellow
}

# Check 4: App Runner Service Status
Write-Host "`n=== Checking App Runner Service ===" -ForegroundColor Cyan
try {
    $serviceName = "$StackName-api"
    Write-Host "Service Name: $serviceName" -ForegroundColor Gray
    
    $services = aws apprunner list-services --region $Region --output json | ConvertFrom-Json
    $service = $services.ServiceSummaryList | Where-Object { $_.ServiceName -eq $serviceName }
    
    if ($service) {
        Write-Host "Service Status: $($service.Status)" -ForegroundColor $(if ($service.Status -eq "RUNNING") { "Green" } else { "Yellow" })
        
        # Get detailed service info
        $serviceDetails = aws apprunner describe-service --service-arn $service.ServiceArn --region $Region --output json | ConvertFrom-Json
        $serviceConfig = $serviceDetails.Service
        
        Write-Host "`nService Configuration:" -ForegroundColor Cyan
        Write-Host "  CPU: $($serviceConfig.InstanceConfiguration.Cpu)" -ForegroundColor Gray
        Write-Host "  Memory: $($serviceConfig.InstanceConfiguration.Memory)" -ForegroundColor Gray
        Write-Host "  Health Check: $($serviceConfig.HealthCheckConfiguration.Path)" -ForegroundColor Gray
        
        # Check environment variables
        Write-Host "`nEnvironment Variables:" -ForegroundColor Cyan
        $envVars = $serviceConfig.SourceConfiguration.ImageRepository.ImageConfiguration.RuntimeEnvironmentVariables
        foreach ($env in $envVars) {
            if ($env.Name -eq "CORS_ORIGINS") {
                Write-Host "  CORS_ORIGINS: $($env.Value)" -ForegroundColor Gray
            }
            if ($env.Name -eq "DATABASE_URL") {
                Write-Host "  DATABASE_URL: [CONFIGURED]" -ForegroundColor Gray
            }
            if ($env.Name -eq "LLM_BACKEND") {
                Write-Host "  LLM_BACKEND: $($env.Value)" -ForegroundColor Gray
            }
        }
    } else {
        Write-Host "✗ Service not found" -ForegroundColor Red
    }
} catch {
    Write-Host "⚠ Could not fetch App Runner details" -ForegroundColor Yellow
    Write-Host "  Error: $($_.Exception.Message)" -ForegroundColor Gray
}

# Check 5: CloudWatch Logs
Write-Host "`n=== Checking CloudWatch Logs ===" -ForegroundColor Cyan
try {
    $logGroups = aws logs describe-log-groups --region $Region --output json | ConvertFrom-Json
    $appRunnerLogs = $logGroups.logGroups | Where-Object { $_.logGroupName -like "*apprunner*$serviceName*" }
    
    if ($appRunnerLogs) {
        Write-Host "Found App Runner log group: $($appRunnerLogs[0].logGroupName)" -ForegroundColor Green
        
        # Get recent log streams
        $streams = aws logs describe-log-streams `
            --log-group-name $appRunnerLogs[0].logGroupName `
            --order-by LastEventTime `
            --descending `
            --max-items 1 `
            --region $Region --output json | ConvertFrom-Json
        
        if ($streams.logStreams) {
            $latestStream = $streams.logStreams[0].logStreamName
            Write-Host "Latest log stream: $latestStream" -ForegroundColor Gray
            
            # Get recent logs
            Write-Host "`nRecent Logs (last 10 events):" -ForegroundColor Cyan
            $logs = aws logs get-log-events `
                --log-group-name $appRunnerLogs[0].logGroupName `
                --log-stream-name $latestStream `
                --limit 10 `
                --region $Region --output json | ConvertFrom-Json
            
            foreach ($event in $logs.events) {
                $timestamp = [DateTimeOffset]::FromUnixTimeMilliseconds($event.timestamp).LocalDateTime
                Write-Host "[$timestamp] $($event.message)" -ForegroundColor Gray
            }
        }
    } else {
        Write-Host "⚠ No App Runner logs found yet" -ForegroundColor Yellow
    }
} catch {
    Write-Host "⚠ Could not fetch logs" -ForegroundColor Yellow
    Write-Host "  Error: $($_.Exception.Message)" -ForegroundColor Gray
}

# Check 6: RDS Database
Write-Host "`n=== Checking RDS Database ===" -ForegroundColor Cyan
try {
    $dbInstances = aws rds describe-db-instances --region $Region --output json | ConvertFrom-Json
    $db = $dbInstances.DBInstances | Where-Object { $_.DBInstanceIdentifier -eq "$StackName-db" }
    
    if ($db) {
        Write-Host "DB Status: $($db.DBInstanceStatus)" -ForegroundColor $(if ($db.DBInstanceStatus -eq "available") { "Green" } else { "Yellow" })
        Write-Host "  Engine: $($db.Engine) $($db.EngineVersion)" -ForegroundColor Gray
        Write-Host "  Endpoint: $($db.Endpoint.Address)" -ForegroundColor Gray
        Write-Host "  Port: $($db.Endpoint.Port)" -ForegroundColor Gray
    } else {
        Write-Host "✗ Database not found" -ForegroundColor Red
    }
} catch {
    Write-Host "⚠ Could not fetch RDS details" -ForegroundColor Yellow
}

# Check 7: S3 Buckets
Write-Host "`n=== Checking S3 Buckets ===" -ForegroundColor Cyan
try {
    # Check frontend bucket
    $frontendFiles = aws s3 ls "s3://$FrontendBucket" --region $Region 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ Frontend bucket accessible" -ForegroundColor Green
        $fileCount = ($frontendFiles | Measure-Object).Count
        Write-Host "  Files: $fileCount" -ForegroundColor Gray
    } else {
        Write-Host "✗ Frontend bucket not accessible" -ForegroundColor Red
    }
    
    # Check storage bucket
    $storageFiles = aws s3 ls "s3://$StorageBucket" --region $Region 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ Storage bucket accessible" -ForegroundColor Green
    } else {
        Write-Host "✗ Storage bucket not accessible" -ForegroundColor Red
    }
} catch {
    Write-Host "⚠ Could not check S3 buckets" -ForegroundColor Yellow
}

# Check 8: ECS Worker
Write-Host "`n=== Checking ECS Worker ===" -ForegroundColor Cyan
try {
    $clusterName = "$StackName-cluster"
    $services = aws ecs list-services --cluster $clusterName --region $Region --output json 2>&1 | ConvertFrom-Json
    
    if ($services.serviceArns) {
        Write-Host "✓ Worker service found" -ForegroundColor Green
        
        $serviceDetails = aws ecs describe-services `
            --cluster $clusterName `
            --services $services.serviceArns[0] `
            --region $Region --output json | ConvertFrom-Json
        
        $service = $serviceDetails.services[0]
        Write-Host "  Running Tasks: $($service.runningCount)" -ForegroundColor Gray
        Write-Host "  Desired Tasks: $($service.desiredCount)" -ForegroundColor Gray
        Write-Host "  Status: $($service.status)" -ForegroundColor Gray
    } else {
        Write-Host "⚠ No worker services found" -ForegroundColor Yellow
    }
} catch {
    Write-Host "⚠ Could not check ECS worker" -ForegroundColor Yellow
}

# Summary and Recommendations
Write-Host "`n=== Diagnostic Summary ===" -ForegroundColor Cyan
Write-Host "`nCommon Issues and Solutions:" -ForegroundColor Yellow

Write-Host "`n1. CORS Errors:" -ForegroundColor White
Write-Host "   - Ensure CORS_ORIGINS environment variable matches your frontend URL"
Write-Host "   - Check App Runner environment variables above"
Write-Host "   - Frontend must use exact URL from CloudFormation output"

Write-Host "`n2. 500 Internal Server Errors:" -ForegroundColor White
Write-Host "   - Check CloudWatch logs for Python tracebacks"
Write-Host "   - Verify DATABASE_URL is correct"
Write-Host "   - Ensure AWS Bedrock is accessible in your region"
Write-Host "   - Check S3 bucket permissions"

Write-Host "`n3. Service Not Starting:" -ForegroundColor White
Write-Host "   - Check if Docker image was pushed to ECR"
Write-Host "   - Verify App Runner has permissions to pull from ECR"
Write-Host "   - Check health check configuration"

Write-Host "`n4. Database Connection Issues:" -ForegroundColor White
Write-Host "   - Verify RDS is in 'available' status"
Write-Host "   - Check security group allows connections from App Runner"
Write-Host "   - Verify DATABASE_URL format is correct"

Write-Host "`nFor detailed logs, run:" -ForegroundColor Cyan
Write-Host "  aws logs tail /aws/apprunner/$serviceName/service --follow --region $Region" -ForegroundColor Gray

Write-Host ""
