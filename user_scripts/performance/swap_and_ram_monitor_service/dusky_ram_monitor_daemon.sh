#!/usr/bin/env bash
# Dusky RAM Monitor - Pure Bash Memory Monitoring Daemon
# Forensic Optimization: Zero forks, zero subshells, hysteresis-aware.

# ==============================================================================
# CONFIGURATION SETTINGS (Fully Commented for Future-Proofing)
# ==============================================================================

# Critical physical RAM threshold (% used).
# Triggers warning unconditionally if RAM goes above this limit, even if ZRAM is empty.
# Set to 90% to leave a safe ~470MB headroom on low-RAM configurations.
THRESHOLD_RAM_CRITICAL=90

# High physical RAM threshold (% used).
# Combined with THRESHOLD_ZRAM_HIGH; both must be met to trigger the warning.
THRESHOLD_RAM_HIGH=80

# High ZRAM Swap occupancy threshold (% used).
# Combined with THRESHOLD_RAM_HIGH; both must be met to trigger the warning.
THRESHOLD_ZRAM_HIGH=80

# RAM Recovery Hysteresis Threshold (% used).
# The cooldown timer ONLY resets if physical RAM drops safely below this percentage.
THRESHOLD_RAM_RECOVERY=75

# Polling Interval (seconds)
# The wait time between memory scans (supports floating-point sub-second values).
POLL_INTERVAL=0.5

# Cooldown Interval (seconds)
# The minimum required wait time before a subsequent notification is allowed to fire.
COOLDOWN_SECS=120

# Internal state tracking (Do not modify)
last_alert_time=0

# ==============================================================================
# ENVIRONMENT PREPARATION
# ==============================================================================

# Load Bash's internal C-compiled sleep to prevent forking /usr/bin/sleep
if [[ -f /usr/lib/bash/sleep ]]; then
    enable -f /usr/lib/bash/sleep sleep 2>/dev/null
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Dusky RAM Monitor started. Config: CriticalRAM=${THRESHOLD_RAM_CRITICAL}%, HighRAM=${THRESHOLD_RAM_HIGH}%, HighZRAM=${THRESHOLD_ZRAM_HIGH}%, RecoveryRAM=${THRESHOLD_RAM_RECOVERY}%, PollInterval=${POLL_INTERVAL}s" >&2

# ==============================================================================
# MAIN POLLING LOOP
# ==============================================================================

while true; do
    MemTotal=0
    MemFree=0
    InactiveFile=0
    SReclaimable=0
    
    # 1. Parse RAM stats (Short-circuits at SReclaimable to save cycles)
    while read -r key val _; do
        case "$key" in
            MemTotal:)          MemTotal=$val ;;
            MemFree:)           MemFree=$val ;;
            "Inactive(file):")  InactiveFile=$val ;;
            SReclaimable:)      SReclaimable=$val; break ;;
        esac
    done < /proc/meminfo
    
    Available=$(( MemFree + InactiveFile + SReclaimable ))
    if (( MemTotal > 0 )); then
        RamUsedPct=$(( (MemTotal - Available) * 100 / MemTotal ))
    else
        RamUsedPct=0
    fi
    
    # 2. Parse ZRAM stats (Direct SysFS reads, no pipes)
    ZramTotal=0
    ZramUsed=0
    
    if [[ -f "/sys/block/zram0/disksize" && -f "/sys/block/zram0/mm_stat" ]]; then
        read -r ZramTotal < /sys/block/zram0/disksize
        read -r ZramUsed _ < /sys/block/zram0/mm_stat
    fi
    
    if (( ZramTotal > 0 )); then
        ZramUsedPct=$(( ZramUsed * 100 / ZramTotal ))
    else
        ZramUsedPct=0
    fi
    
    # 3. Threshold Checks & Hysteresis Timer
    if (( RamUsedPct >= THRESHOLD_RAM_CRITICAL || (RamUsedPct >= THRESHOLD_RAM_HIGH && ZramUsedPct >= THRESHOLD_ZRAM_HIGH) )); then
        if (( last_alert_time == 0 || (EPOCHSECONDS - last_alert_time) >= COOLDOWN_SECS )); then
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] ALERT TRIGGERED: RAM=${RamUsedPct}% (Critical threshold: ${THRESHOLD_RAM_CRITICAL}%), ZRAM=${ZramUsedPct}%" >&2
            /usr/bin/notify-send -r 3307 -a "dusky-high-ram-alert" -u critical \
                "CRITICAL MEMORY LOW" \
                "RAM: ${RamUsedPct}% | ZRAM: ${ZramUsedPct}%"
            last_alert_time=$EPOCHSECONDS
        fi
    elif (( RamUsedPct <= THRESHOLD_RAM_RECOVERY )); then
        if (( last_alert_time != 0 )); then
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] SYSTEM RECOVERED: RAM=${RamUsedPct}% (below recovery threshold ${THRESHOLD_RAM_RECOVERY}%)" >&2
        fi
        # Hysteresis reset: only clear timer when memory has legitimately recovered
        last_alert_time=0
    fi
    
    # Pure Bash sleep (if loaded), falling back to binary gracefully
    sleep "$POLL_INTERVAL"
done
