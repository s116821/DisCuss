# Run from an extracted archive in an elevated Windows PowerShell session.
[CmdletBinding()]
param(
    [ValidateSet('Install','Rollback','Uninstall')][string] $Operation = 'Install',
    [string] $Root = (Join-Path $env:ProgramData 'DisCuss'),
    [string] $TaskName = 'DisCuss',
    [switch] $Plan, [switch] $ProvisionOnly
)
$ErrorActionPreference = 'Stop'
$bundle = $PSScriptRoot
$Root = [IO.Path]::GetFullPath($Root).TrimEnd('\')
if ($Root -eq [IO.Path]::GetPathRoot($Root) -or $Root.Contains('"')) { throw 'Unsafe install root' }
if ($TaskName -notmatch '^DisCuss(?:-[A-Za-z0-9]+)?$') { throw 'Use a dedicated DisCuss task name' }
function Managed([string] $Path) {
    $resolved = [IO.Path]::GetFullPath($Path)
    if ($resolved -ne $Root -and -not $resolved.StartsWith($Root+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Path escapes install root' }
    $probe = $resolved
    while ($probe -and $probe.Length -ge $Root.Length) {
        if ((Test-Path -LiteralPath $probe) -and ((Get-Item -LiteralPath $probe).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Managed paths cannot contain reparse points' }
        $probe = Split-Path $probe -Parent
    }
    return $resolved
}
function Protect([string] $Path, [string] $RuntimeRights = 'ReadAndExecute') {
    Managed $Path | Out-Null
    $item = Get-Item -LiteralPath $Path
    $acl = if ($item.PSIsContainer) { New-Object Security.AccessControl.DirectorySecurity } else { New-Object Security.AccessControl.FileSecurity }
    $acl.SetAccessRuleProtection($true,$false)
    $acl.SetOwner((New-Object Security.Principal.SecurityIdentifier 'S-1-5-32-544'))
    $inherit = if ($item.PSIsContainer) { [Security.AccessControl.InheritanceFlags]'ContainerInherit,ObjectInherit' } else { [Security.AccessControl.InheritanceFlags]::None }
    foreach ($entry in @(@('S-1-5-18','FullControl'),@('S-1-5-32-544','FullControl'),@('S-1-5-19',$RuntimeRights))) {
        if ($entry[1] -eq 'None') { continue }
        $rule = New-Object Security.AccessControl.FileSystemAccessRule((New-Object Security.Principal.SecurityIdentifier $entry[0]),$entry[1],$inherit,[Security.AccessControl.PropagationFlags]::None,[Security.AccessControl.AccessControlType]::Allow)
        $acl.AddAccessRule($rule)
    }
    Set-Acl -LiteralPath $Path -AclObject $acl
}
function Checked([string] $Program, [string[]] $Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw 'Runtime provisioning/recovery failed; prior startup remains recoverable' }
}
$config = Managed (Join-Path $Root 'config.json')
$state = Managed (Join-Path $Root 'state')
$currentFile = Managed (Join-Path $Root 'current.json')
$previousFile = Managed (Join-Path $Root 'previous.json')
$current = if (Test-Path -LiteralPath $currentFile) { Get-Content -LiteralPath $currentFile -Raw | ConvertFrom-Json } else { $null }
$manifest = $null
if ($Operation -eq 'Install') {
    $manifest = Get-Content -LiteralPath (Join-Path $bundle 'manifest.json') -Raw | ConvertFrom-Json
    if ($manifest.platform -ne 'windows-x64' -or $manifest.tag -ne ('v'+$manifest.version) -or $manifest.version -notmatch '^\d+\.\d+\.\d+(?:[a-zA-Z0-9.+-]*)$') { throw 'Invalid Windows bundle identity' }
    foreach ($file in $manifest.files.PSObject.Properties) {
        if ([IO.Path]::GetFileName($file.Name) -ne $file.Name -or (Get-FileHash -LiteralPath (Join-Path $bundle $file.Name) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.Value) { throw 'Bundle integrity failure' }
    }
}
if ($Plan) {
    [pscustomobject]@{Operation=$Operation;Root=$Root;Task=$TaskName;Identity='S-1-5-19';Trigger='AtStartup';ExecutionTimeLimit='Unlimited';MultipleInstances='IgnoreNew';Python='3.12.15';State=$state} | ConvertTo-Json
    return
}
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Run elevated; -Plan is read-only' }
Managed $Root | Out-Null
New-Item -ItemType Directory -Path $Root -Force | Out-Null
Protect $Root
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing -and ($existing.Description -ne 'DisCuss managed single-process runtime' -or -not $current)) { throw 'Existing task is not installer-owned' }
$wasRunning = $existing -and $existing.State -eq 'Running'
$savedTask = if ($existing) { Export-ScheduledTask -TaskName $TaskName } else { $null }
if ($existing) {
    Stop-ScheduledTask -TaskName $TaskName
    $deadline = (Get-Date).AddSeconds(60)
    while ((Get-ScheduledTask -TaskName $TaskName).State -eq 'Running') {
        if ((Get-Date) -gt $deadline) { throw 'Task did not stop; resolve before installation' }
        Start-Sleep -Milliseconds 250
    }
}
if ($Operation -eq 'Uninstall') {
    if ($existing) { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false }
    Write-Output 'Startup removed. Config/state/models/releases/recovery snapshots retained.'
    return
}
$switched = $false
$activated = $false
$previousConfigReady = $false
try {
    New-Item -ItemType Directory -Path $state -Force | Out-Null
    Protect $state 'Modify'
    $backups = Managed (Join-Path $Root 'backups')
    New-Item -ItemType Directory -Path $backups -Force | Out-Null
    Protect $backups 'None'
    $snapshot = Managed (Join-Path $backups ([guid]::NewGuid().ToString()))
    if ($current) {
        Managed $current.python | Out-Null
        Managed $current.helper | Out-Null
        & $current.python -m discuss.cli --config $config doctor | Out-Null
        $previousConfigReady = $LASTEXITCODE -eq 0
        Checked $current.python @($current.helper,'backup','--config',$config,'--state',$state,'--snapshot',$snapshot)
        if ($savedTask) { $savedTask | Set-Content -LiteralPath (Join-Path $snapshot 'task.xml') -Encoding Unicode }
    }
    if ($Operation -eq 'Rollback') {
        if (-not $current -or -not (Test-Path -LiteralPath $previousFile)) { throw 'No previous recovery snapshot' }
        $candidate = Get-Content -LiteralPath $previousFile -Raw | ConvertFrom-Json
        Managed $candidate.python | Out-Null
        Managed $candidate.helper | Out-Null
        Managed $candidate.snapshot | Out-Null
        Checked $candidate.python @($candidate.helper,'restore','--config',$config,'--state',$state,'--snapshot',$candidate.snapshot)
    } else {
        $tools = Managed (Join-Path $Root 'tools')
        New-Item -ItemType Directory -Path $tools -Force | Out-Null
        $archive = Managed (Join-Path $tools 'uv-0.13.0.zip')
        Invoke-WebRequest 'https://github.com/astral-sh/uv/releases/download/0.13.0/uv-x86_64-pc-windows-msvc.zip' -OutFile $archive -UseBasicParsing
        if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne '088962f9e7b7bd9ea740c04c650b2a21c8928c345bd99ac24350dc924dba656c') { throw 'uv checksum mismatch' }
        $uvDirectory = Managed (Join-Path $tools 'uv-0.13.0')
        Expand-Archive -LiteralPath $archive -DestinationPath $uvDirectory -Force
        $uv = Join-Path $uvDirectory 'uv.exe'
        $env:UV_PYTHON_INSTALL_DIR = Managed (Join-Path $Root 'python')
        $env:UV_CACHE_DIR = Managed (Join-Path $Root 'cache')
        $env:UV_PYTHON_BIN_DIR = Managed (Join-Path $tools 'python-bin')
        Checked $uv @('python','install','3.12.15')
        $release = Managed (Join-Path $Root ('releases\'+$manifest.version))
        if (Test-Path -LiteralPath (Join-Path $release 'manifest.json')) {
            if ((Get-FileHash (Join-Path $release 'manifest.json')).Hash -ne (Get-FileHash (Join-Path $bundle 'manifest.json')).Hash) { throw 'Version collision; runtime cannot be overwritten' }
        }
        New-Item -ItemType Directory -Path $release -Force | Out-Null
        Copy-Item -LiteralPath (Join-Path $bundle 'manage_state.py') -Destination $release
        $venv = Join-Path $release 'venv'
        if (-not (Test-Path -LiteralPath (Join-Path $venv 'Scripts\python.exe'))) { Checked $uv @('venv','--managed-python','--python','3.12.15',$venv) }
        $python = Join-Path $venv 'Scripts\python.exe'
        if (-not $current -and ((Test-Path -LiteralPath $config) -or (Test-Path -LiteralPath (Join-Path $state 'statistics.sqlite3')))) { Checked $python @((Join-Path $release 'manage_state.py'),'backup','--config',$config,'--state',$state,'--snapshot',$snapshot) }
        $installArgs = @('pip','install','--python',$python,'--require-hashes','-r',(Join-Path $bundle 'runtime-requirements.txt'))
        $requiresBuild = if ($null -ne $manifest.receiver_requires_build) { $manifest.receiver_requires_build } else { -not $manifest.qualified_dependency }
        if (-not $requiresBuild) { $installArgs += @('--only-binary',':all:') }
        Checked $uv $installArgs
        $wheel = @(Get-ChildItem -LiteralPath $bundle -Filter '*.whl')
        if ($wheel.Count -ne 1) { throw 'Expected exactly one application wheel' }
        Checked $uv @('pip','install','--python',$python,'--no-deps',$wheel[0].FullName)
        Checked $python @('-c','import importlib.metadata,sys; assert importlib.metadata.version("discuss")==sys.argv[1]',$manifest.version)
        Checked $python @('-c','import av, numpy, faster_whisper; from discord.opus import Decoder; Decoder(); import discuss.application')
        if (-not (Test-Path -LiteralPath $config)) {
            $example = Get-Content -LiteralPath (Join-Path $bundle 'config.example.json') -Raw | ConvertFrom-Json
            $example.state_dir = $state
            $example | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $config -Encoding UTF8
        }
        $configured = Get-Content -LiteralPath $config -Raw | ConvertFrom-Json
        $configuredState = if ([IO.Path]::IsPathRooted($configured.state_dir)) { $configured.state_dir } else { Join-Path $Root $configured.state_dir }
        if ([IO.Path]::GetFullPath($configuredState) -ne $state) { throw 'Config state_dir must resolve to managed state' }
        Copy-Item -LiteralPath (Join-Path $bundle 'manifest.json') -Destination $release
        $candidate = [pscustomobject]@{python=$python;helper=(Join-Path $release 'manage_state.py');version=$manifest.version;snapshot=$snapshot}
    }
    Protect $config 'Read'
    & $candidate.python -m discuss.cli --config $config doctor | Out-Null
    if ($LASTEXITCODE -eq 0) { Checked $candidate.python @('-m','discuss.cli','--config',$config,'doctor','--runtime') }
    elseif ($previousConfigReady) { throw 'Candidate rejects previously valid configuration; upgrade aborted' }
    if (-not $ProvisionOnly) {
        $action = New-ScheduledTaskAction -Execute $candidate.python -Argument ('-m discuss.cli --config "'+$config+'" --log-file "'+(Join-Path $state 'runtime.log')+'" run') -WorkingDirectory $Root
        $trigger = New-ScheduledTaskTrigger -AtStartup
        $identity = New-ScheduledTaskPrincipal -UserId 'S-1-5-19' -LogonType ServiceAccount -RunLevel Limited
        $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -StartWhenAvailable -RunOnlyIfNetworkAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
        Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $identity -Settings $settings -Description 'DisCuss managed single-process runtime' -Force | Out-Null
    }
    if ($current -and $Operation -eq 'Install' -and $current.version -ne $candidate.version) { $current.snapshot=$snapshot; $current | ConvertTo-Json | Set-Content -LiteralPath $previousFile -Encoding UTF8 }
    $candidate | ConvertTo-Json | Set-Content -LiteralPath $currentFile -Encoding UTF8
    if (-not $ProvisionOnly) {
        $activated = $true
        Start-ScheduledTask -TaskName $TaskName
        Start-Sleep -Seconds 2
        $running = (Get-ScheduledTask -TaskName $TaskName).State -eq 'Running'
        $result = (Get-ScheduledTaskInfo -TaskName $TaskName).LastTaskResult
        if (-not $running -and $result -ne 0 -and $result -ne 267009) { throw 'Candidate startup failed' }
    }
    $switched = $true
    Write-Output 'Installed. Edit protected config, prepare model explicitly, run doctor --runtime, then start task.'
} finally {
    if (-not $switched) {
        if ($activated) {
            Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
            if ($current -and (Test-Path -LiteralPath (Join-Path $snapshot 'statistics.sqlite3'))) { Checked $current.python @($current.helper,'restore','--config',$config,'--state',$state,'--snapshot',$snapshot) }
            if ($current) { $current | ConvertTo-Json | Set-Content -LiteralPath $currentFile -Encoding UTF8 }
        }
        if ($savedTask) {
            Register-ScheduledTask -TaskName $TaskName -Xml $savedTask -Force | Out-Null
            if ($wasRunning) { Start-ScheduledTask -TaskName $TaskName }
        }
    }
}
