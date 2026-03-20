param(
    [switch]$OneDir,
    [switch]$NoClean
)

$argsList = @("scripts/build_release.py")

if ($OneDir) {
    $argsList += "--onedir"
}

if ($NoClean) {
    $argsList += "--no-clean"
}

if (Get-Command py -ErrorAction SilentlyContinue) {
    & py @argsList
} else {
    & python @argsList
}
