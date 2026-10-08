param([Parameter(Mandatory=$true)][string]$ArchiveDirectory)
$ErrorActionPreference = 'Stop'
$archives = @(Get-ChildItem -LiteralPath $ArchiveDirectory -Filter '*windows-x86_64.7z')
if ($archives.Count -ne 1) { throw 'Expected exactly one Windows core archive' }
$temporary = Join-Path ([IO.Path]::GetTempPath()) ('sh-runtime-' + [guid]::NewGuid().ToString())
$reports = Join-Path $PSScriptRoot '../test-results/windows-runtime'
New-Item -ItemType Directory -Force $reports | Out-Null
try {
    & 7z x -y "-o$temporary" $archives[0].FullName | Out-Null
    if ($LASTEXITCODE) { throw 'Archive extraction failed' }
    $cores = @(Get-ChildItem -LiteralPath $temporary -Recurse -Filter shmdp_libretro.dll)
    if ($cores.Count -ne 1) { throw 'Expected exactly one core DLL' }
    foreach ($threaded in @($false, $true)) {
        $mode = if ($threaded) { 'threaded' } else { 'single' }
        $arguments = @((Join-Path $PSScriptRoot '../tests/libretro_public_smoke.py'),
                       '--core', $cores[0].FullName, '--output', (Join-Path $reports "$mode.json"))
        if ($threaded) { $arguments += '--threaded' }
        & python @arguments *> (Join-Path $reports "$mode.log")
        if ($LASTEXITCODE) { throw "Windows $mode smoke test failed; see $mode.log" }
    }
} finally {
    if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Recurse -Force }
}

