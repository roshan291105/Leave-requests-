$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'src\main\java\com\leavems\LeaveManagementApp.java'
$out = Join-Path $PSScriptRoot 'out'
New-Item -ItemType Directory -Force -Path $out | Out-Null
javac -encoding UTF-8 -d $out $source
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
java -cp $out com.leavems.LeaveManagementApp
