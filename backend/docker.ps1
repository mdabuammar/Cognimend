# Quick Docker wrapper - adds Docker to PATH and runs the command
$env:PATH += ";C:\Program Files\Docker\Docker\resources\bin"
& docker $args
