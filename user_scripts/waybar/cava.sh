#!/bin/bash
set -o pipefail

bars=18
vert=0
clean=0

usage() {
    local fd=1
    (( ${1:-0} )) && fd=2
    printf 'Usage: %s [--vert] [--clean] [--bars N | --N]\n' "${0##*/}" >&$fd
    exit "${1:-0}"
}

validate_bars() {
    [[ $1 =~ ^[0-9]+$ ]] && (( $1 >= 1 )) || {
        printf 'Invalid bar count: %s\n' "$1" >&2
        exit 1
    }
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help) usage 0 ;;
        --vert) vert=1 ;;
        --clean) clean=1 ;;
        --bars)
            [[ -n ${2+x} ]] || { printf 'Missing value for --bars\n' >&2; exit 1; }
            bars="$2"; shift
            validate_bars "$bars"
            ;;
        --bars=*)
            bars="${1#--bars=}"
            validate_bars "$bars"
            ;;
        --[0-9]*)
            bars="${1#--}"
            validate_bars "$bars"
            ;;
        *)
            printf 'Unknown option: %s\n' "$1" >&2
            usage 1
            ;;
    esac
    shift
done

command -v cava >/dev/null 2>&1 || {
    printf 'cava: command not found\n' >&2
    exit 1
}

trap 'kill 0 2>/dev/null' EXIT

# ascii_max_range = 7 corresponds to the 8 block characters below (0-7 → ▁▂▃▄▅▆▇█)
cava -p <(cat << EOF
[general]
bars = $bars
framerate = 60

[output]
method = raw
raw_target = /dev/stdout
data_format = ascii
ascii_max_range = 7
EOF
) | if (( vert )); then
    awk -v clean="$clean" '
BEGIN {
    m["0"]="▁"; m["1"]="▂"; m["2"]="▃"; m["3"]="▄"
    m["4"]="▅"; m["5"]="▆"; m["6"]="▇"; m["7"]="█"
}
{
    out = ""
    n = split($0, a, ";")
    all_zero = 1
    for (i = 1; i <= n; i++) {
        if (a[i] in m) {
            if (a[i] != "0") all_zero = 0
            if (out != "") out = out "\\n"
            out = out m[a[i]]
        }
    }
    if (clean && all_zero) out = ""
    printf "{\"text\":\"%s\"}\n", out
    fflush()
}'
else
    if (( clean )); then
        sed -u 's/;//g;y/01234567/▁▂▃▄▅▆▇█/' | sed -u '/^▁*$/s/.*//'
    else
        sed -u 's/;//g;y/01234567/▁▂▃▄▅▆▇█/'
    fi
fi
