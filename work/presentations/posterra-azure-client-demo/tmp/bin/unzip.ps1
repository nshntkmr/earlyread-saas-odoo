param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ArgsList
)

Add-Type -AssemblyName System.IO.Compression.FileSystem

if ($ArgsList.Count -lt 2) {
    Write-Error "Usage: unzip -Z1 <zip> OR unzip -p <zip> <entry>"
    exit 1
}

$mode = $ArgsList[0]
$zipPath = $ArgsList[1]

try {
    $zip = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
    try {
        if ($mode -eq '-Z1') {
            foreach ($entry in $zip.Entries) {
                [Console]::Out.WriteLine($entry.FullName)
            }
            exit 0
        }

        if ($mode -eq '-p') {
            if ($ArgsList.Count -lt 3) {
                Write-Error "Missing zip entry for -p"
                exit 1
            }
            $entryName = $ArgsList[2]
            $entry = $zip.Entries | Where-Object { $_.FullName -eq $entryName } | Select-Object -First 1
            if (-not $entry) {
                Write-Error "Entry not found: $entryName"
                exit 1
            }
            $stream = $entry.Open()
            try {
                $out = [Console]::OpenStandardOutput()
                $buffer = New-Object byte[] 81920
                while (($read = $stream.Read($buffer, 0, $buffer.Length)) -gt 0) {
                    $out.Write($buffer, 0, $read)
                }
                $out.Flush()
            } finally {
                $stream.Dispose()
            }
            exit 0
        }

        Write-Error "Unsupported unzip mode: $mode"
        exit 1
    } finally {
        $zip.Dispose()
    }
} catch {
    Write-Error $_.Exception.Message
    exit 1
}
