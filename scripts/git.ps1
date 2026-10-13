param([Parameter(ValueFromRemainingArguments = $true)][string[]] $GitArgs)
# PowerShell loads the user's profiles before this script. Do not call git.exe.
git @GitArgs
exit $LASTEXITCODE
