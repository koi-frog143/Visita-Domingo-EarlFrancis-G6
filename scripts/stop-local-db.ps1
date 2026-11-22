$ErrorActionPreference = 'Stop'
$visitaRoot = Split-Path -Parent $PSScriptRoot
$visitaData = Join-Path $visitaRoot '.local/postgres'
if (!(Test-Path -LiteralPath (Join-Path $visitaData 'PG_VERSION'))) {
    throw 'No prepared Visita database exists in this repository.'
}
& 'C:/Program Files/PostgreSQL/18/bin/pg_ctl.exe' -D $visitaData -m fast stop
if ($LASTEXITCODE -ne 0) { throw 'Could not stop the Visita local database.' }
