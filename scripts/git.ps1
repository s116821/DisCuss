# PowerShell loads the user's profiles before this script. Do not call git.exe.
git @args
exit $LASTEXITCODE
