$ErrorActionPreference = 'Stop'
$visitaRoot = Split-Path -Parent $PSScriptRoot
$visitaData = Join-Path $visitaRoot '.local/postgres'
$visitaPgCtl = 'C:/Program Files/PostgreSQL/18/bin/pg_ctl.exe'
if (!(Test-Path -LiteralPath (Join-Path $visitaData 'PG_VERSION'))) {
    throw 'The prepared local database is missing. Follow the fresh clone instructions in README.md.'
}
& $visitaPgCtl -D $visitaData status *> $null
if ($LASTEXITCODE -eq 0) { Write-Output 'Visita local database is already running.'; exit 0 }
& $visitaPgCtl -D $visitaData -l (Join-Path $visitaRoot '.local/postgres.log') -o '-h 127.0.0.1 -p 55439' start
if ($LASTEXITCODE -ne 0) { throw 'Could not start the Visita local database.' }
