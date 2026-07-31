[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$commit = 'e81e9b65c4b35fc8f7f2993a81e25e0bc24608db'
$toolRoot = Join-Path $env:USERPROFILE '.codex\tools\baidupcs-py'
$sourceDir = Join-Path $toolRoot 'src'
$marker = Join-Path $toolRoot 'installed-commit.txt'
$pythonMarker = Join-Path $toolRoot 'python-path.txt'
$remote = 'https://github.com/PeterDing/BaiduPCS-Py.git'

function Find-CompatiblePython {
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($launcher) {
        foreach ($selector in @('-3.12', '-3.11', '-3.10', '-3.9')) {
            $candidate = (& $launcher.Source $selector -c 'import sys; print(sys.executable)' 2>$null)
            if ($LASTEXITCODE -eq 0 -and $candidate) {
                $path = $candidate.Trim()
                if (Test-Path -LiteralPath $path) {
                    return $path
                }
            }
        }
    }

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        $candidate = (& $pythonCommand.Source -c 'import sys; assert (3, 9) <= sys.version_info[:2] <= (3, 12); print(sys.executable)' 2>$null)
        if ($LASTEXITCODE -eq 0 -and $candidate) {
            return $candidate.Trim()
        }
    }

    throw 'Python 3.9-3.12 is required. Install it from https://www.python.org/downloads/windows/.'
}

New-Item -ItemType Directory -Path $toolRoot -Force | Out-Null

if (-not (Test-Path -LiteralPath (Join-Path $sourceDir '.git'))) {
    & git clone $remote $sourceDir
    if ($LASTEXITCODE -ne 0) {
        if (Test-Path -LiteralPath $sourceDir) {
            $resolvedSource = [IO.Path]::GetFullPath($sourceDir)
            $resolvedRoot = [IO.Path]::GetFullPath($toolRoot)
            if (-not $resolvedSource.StartsWith($resolvedRoot + [IO.Path]::DirectorySeparatorChar)) {
                throw 'Refusing to remove an unexpected partial clone path.'
            }
            [IO.Directory]::Delete($resolvedSource, $true)
        }
        & git -c http.proxy= -c https.proxy= clone $remote $sourceDir
    }
    if ($LASTEXITCODE -ne 0) {
        throw 'Unable to clone PeterDing/BaiduPCS-Py.'
    }
}

& git -C $sourceDir checkout --force $commit
if ($LASTEXITCODE -ne 0) {
    & git -C $sourceDir -c http.proxy= -c https.proxy= fetch origin $commit
    & git -C $sourceDir checkout --force $commit
}
if ($LASTEXITCODE -ne 0) {
    throw "Unable to check out BaiduPCS-Py commit $commit."
}

$pcsPath = Join-Path $sourceDir 'baidupcs_py\baidupcs\pcs.py'
$source = [IO.File]::ReadAllText($pcsPath)
$patched = [Text.RegularExpressions.Regex]::Replace(
    $source,
    '(?m)^\s*"limit"\s*:\s*"0-2147483647",\r?\n',
    ''
)
if ($patched -eq $source -and $source.Contains('"limit": "0-2147483647"')) {
    throw 'The known Baidu list-limit compatibility patch could not be applied.'
}
[IO.File]::WriteAllText($pcsPath, $patched, [Text.UTF8Encoding]::new($false))

$cryptoPath = Join-Path $sourceDir 'baidupcs_py\common\crypto.py'
$crypto = [IO.File]::ReadAllText($cryptoPath)
if ($crypto -notmatch 'Encryption is optional for search') {
    $crypto = [Text.RegularExpressions.Regex]::Replace(
        $crypto,
        '(?m)^from cryptography\.hazmat\.primitives\.ciphers import Cipher, algorithms, modes\r?\nfrom cryptography\.hazmat\.primitives\.padding import PKCS7\r?\nfrom cryptography\.hazmat\.backends import default_backend\r?\n',
        "try:`n    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes`n    from cryptography.hazmat.primitives.padding import PKCS7`n    from cryptography.hazmat.backends import default_backend`nexcept ImportError:  # Encryption is optional for search, upload, and share operations.`n    Cipher = algorithms = modes = PKCS7 = default_backend = None`n"
    )
    $simpleCipherFallback = @'
try:
    from baidupcs_py.common.simple_cipher import SimpleCryptography as _SimpleCryptography
except ImportError:  # The Cython extension is only needed by encrypted transfers.
    class _SimpleCryptography:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("Install Cython-built simple_cipher to use encrypted transfers")
'@
    $crypto = $crypto.Replace(
        'from baidupcs_py.common.simple_cipher import SimpleCryptography as _SimpleCryptography',
        $simpleCipherFallback.Trim()
    )
    [IO.File]::WriteAllText($cryptoPath, $crypto, [Text.UTF8Encoding]::new($false))
}

$appInitPath = Join-Path $sourceDir 'baidupcs_py\app\__init__.py'
$appInit = [IO.File]::ReadAllText($appInitPath)
if ($appInit -match 'from baidupcs_py\.app\.app import app as _app') {
    $appInit = [Text.RegularExpressions.Regex]::Replace(
        $appInit,
        '(?m)^from baidupcs_py\.app\.app import app as _app\r?\n',
        ''
    )
    $appInit = [Text.RegularExpressions.Regex]::Replace(
        $appInit,
        '(?m)^def main\(\):\r?\n\s+_app\(obj=SimpleNamespace\(\)\)',
        "def main():`n    from baidupcs_py.app.app import app as _app`n`n    _app(obj=SimpleNamespace())"
    )
    [IO.File]::WriteAllText($appInitPath, $appInit, [Text.UTF8Encoding]::new($false))
}

$python = Find-CompatiblePython

$installedCommit = if (Test-Path -LiteralPath $marker) {
    (Get-Content -LiteralPath $marker -Raw).Trim()
} else {
    ''
}

$env:PYTHONPATH = $sourceDir
$env:PYTHONWARNINGS = 'ignore'
$dependencyProbe = 'import requests, requests_toolbelt, rich, click, passlib, typing_extensions; from PIL import Image; import baidupcs_py'
& $python -c $dependencyProbe
if ($LASTEXITCODE -ne 0) {
    & $python -m ensurepip --upgrade
    & $python -m pip --isolated install --disable-pip-version-check requests requests-toolbelt rich click passlib typing-extensions pillow
    if ($LASTEXITCODE -ne 0) {
        throw 'Failed to install the minimal Python dependencies.'
    }
    & $python -c $dependencyProbe
    if ($LASTEXITCODE -ne 0) {
        throw 'BaiduPCS-Py imports still fail after dependency installation.'
    }
}

if ($installedCommit -ne $commit) {
    Set-Content -LiteralPath $marker -Value $commit -Encoding ascii
}
Set-Content -LiteralPath $pythonMarker -Value $python -Encoding utf8

[pscustomobject]@{
    ok = $true
    commit = $commit
    python = $python
    source = $sourceDir
} | ConvertTo-Json -Compress
