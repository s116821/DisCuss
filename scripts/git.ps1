# PowerShell loads the user's profiles before this script. Do not call git.exe.
$ErrorActionPreference = 'Stop'
for ($attempt = 0; $attempt -lt 3; $attempt++) {
    try {
        git @args
        exit $LASTEXITCODE
    } catch {
        # The workstation identity hook explicitly did not run Git. Retry only
        # this transient identity lookup; never replay a Git operation itself.
        if ($attempt -eq 2 -or $_.Exception.Message -notlike '*Cannot determine the active gh account. Git was not run*') {
            throw
        }
        Start-Sleep -Milliseconds 500
    }
}
