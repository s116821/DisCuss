param([string] $Path)
$ErrorActionPreference = 'Stop'
try {
    $taskAcl = Get-Acl -LiteralPath $Path
    $taskBroadSids = @('S-1-1-0', 'S-1-5-11', 'S-1-5-32-545')
    foreach ($taskRule in $taskAcl.Access) {
        $taskSid = $taskRule.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value
        if ($taskSid -in $taskBroadSids -and $taskRule.AccessControlType -eq 'Allow' -and
            ($taskRule.FileSystemRights -band [Security.AccessControl.FileSystemRights]::ReadData)) { exit 1 }
    }
    exit 0
} catch { exit 1 }
