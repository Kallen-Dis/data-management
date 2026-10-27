param(
    [string]$MongoUri = 'mongodb://127.0.0.1:27018',
    [string]$Database = 'survey_stage2_test',
    [switch]$Mock,
    [switch]$SkipBuild,
    [string]$Npm = 'npm.cmd'
)

$ErrorActionPreference = 'Stop'
if (-not $Database.EndsWith('_test')) { throw '测试数据库名必须以 _test 结尾；测试会清空该库中的项目集合。' }
$Project = Split-Path $PSScriptRoot -Parent
$Python = Join-Path $Project 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) { throw '请先按 README 创建 backend/.venv 并安装依赖。' }
$Names = @('DB_NAME', 'MONGODB_URI', 'SURVEY_TEST_MOCK', 'SSLKEYLOGFILE')
$Previous = @{}
foreach ($Name in $Names) { $Previous[$Name] = [Environment]::GetEnvironmentVariable($Name, 'Process') }
try {
    $env:DB_NAME = $Database
    $env:MONGODB_URI = $MongoUri
    $env:SURVEY_TEST_MOCK = if ($Mock) { '1' } else { $null }
    $env:SSLKEYLOGFILE = $null
    Push-Location (Join-Path $Project 'backend')
    try {
        if (-not $Mock) {
            & $Python -c "import os; from pymongo import MongoClient; client=MongoClient(os.environ['MONGODB_URI'], serverSelectionTimeoutMS=3000); print(client.admin.command('ping'))"
            if ($LASTEXITCODE -ne 0) { throw '请先在独立端口启动测试 MongoDB，或使用 -Mock 进行非聚合回归。' }
        }
        & $Python -m pytest tests -q
        if ($LASTEXITCODE -ne 0) { throw '后端回归失败。' }
    } finally { Pop-Location }
    if (-not $SkipBuild) {
        Push-Location (Join-Path $Project 'frontend')
        try {
            & $Npm run build
            if ($LASTEXITCODE -ne 0) { throw '前端构建失败。' }
        } finally { Pop-Location }
    }
} finally {
    foreach ($Name in $Names) { [Environment]::SetEnvironmentVariable($Name, $Previous[$Name], 'Process') }
}
