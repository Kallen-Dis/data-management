param(
    [string]$MongoExecutable = 'D:\MongoDB\Server\8.3\bin\mongod.exe',
    [string]$Npm = 'npm.cmd'
)

$ErrorActionPreference = 'Stop'
$Project = Split-Path $PSScriptRoot -Parent
$Runtime = Join-Path $Project '.runtime'
$Python = Join-Path $Project 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) { throw '缺少 backend/.venv，请先按 README 安装后端依赖。' }
New-Item -ItemType Directory -Force -Path $Runtime | Out-Null
function Test-LocalPort([int]$Port) {
    $Connection = [System.Net.Sockets.TcpClient]::new()
    try { $Connection.Connect('127.0.0.1', $Port); return $true } catch { return $false } finally { $Connection.Dispose() }
}
if (-not (Test-LocalPort 27017)) {
    if (-not (Test-Path -LiteralPath $MongoExecutable)) {
        $MongoExecutable = (Get-Command mongod.exe -ErrorAction Stop).Source
    }
    $Data = Join-Path $Project '.mongo-data'
    New-Item -ItemType Directory -Force -Path $Data | Out-Null
    Start-Process -FilePath $MongoExecutable -ArgumentList @('--dbpath', ('"' + $Data + '"'), '--port', '27017', '--bind_ip', '127.0.0.1') -WorkingDirectory $Project -WindowStyle Hidden -RedirectStandardOutput (Join-Path $Runtime 'mongo.log') -RedirectStandardError (Join-Path $Runtime 'mongo-error.log') | Out-Null
}
for ($Attempt = 0; $Attempt -lt 30 -and -not (Test-LocalPort 27017); $Attempt++) { Start-Sleep -Milliseconds 500 }
if (-not (Test-LocalPort 27017)) { throw 'MongoDB 启动失败，请检查 .runtime/mongo-error.log。' }
if (-not (Test-LocalPort 8000)) {
    $PreviousUri = $env:MONGODB_URI
    $PreviousDatabase = $env:DB_NAME
    try {
        $env:MONGODB_URI = 'mongodb://127.0.0.1:27017'
        $env:DB_NAME = 'survey_db'
        Start-Process -FilePath $Python -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000') -WorkingDirectory (Join-Path $Project 'backend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $Runtime 'backend.log') -RedirectStandardError (Join-Path $Runtime 'backend-error.log') | Out-Null
    } finally { $env:MONGODB_URI = $PreviousUri; $env:DB_NAME = $PreviousDatabase }
}
if (-not (Test-LocalPort 5173)) {
    $NpmPath = (Get-Command $Npm -ErrorAction Stop).Source
    Start-Process -FilePath $env:ComSpec -ArgumentList @('/d', '/c', ('""' + $NpmPath + '" run dev -- --host 127.0.0.1 --strictPort"')) -WorkingDirectory (Join-Path $Project 'frontend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $Runtime 'frontend.log') -RedirectStandardError (Join-Path $Runtime 'frontend-error.log') | Out-Null
}
for ($Attempt = 0; $Attempt -lt 30 -and (-not (Test-LocalPort 8000) -or -not (Test-LocalPort 5173)); $Attempt++) { Start-Sleep -Milliseconds 500 }
if (-not (Test-LocalPort 8000) -or -not (Test-LocalPort 5173)) { throw '服务未就绪，请检查 .runtime 中的日志。' }
Write-Output '前端：http://127.0.0.1:5173/  接口文档：http://127.0.0.1:8000/docs'
Write-Output '已占用的端口会被保留，不终止其他进程；旧数据库升级请另行运行 migrate_stage2.py。'
