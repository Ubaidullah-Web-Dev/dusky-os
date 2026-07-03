#!/usr/bin/env python3
import os
from pathlib import Path
from typing import Any
from python.frontend.core_types import BaseEngine

RAPL_BASE = Path("/sys/class/powercap")

def safe_read_int(p: Path) -> int | None:
    try:
        return int(p.read_text().strip())
    except (OSError, ValueError):
        return None

def safe_write(p: Path, val: int) -> bool:
    try:
        p.write_text(str(val))
        return True
    except OSError:
        return False

class FastEnergyReader:
    def __init__(self, path: Path):
        try:
            self.fd = os.open(path, os.O_RDONLY)
        except OSError:
            self.fd = None

    def read(self) -> int | None:
        if self.fd is None:
            return None
        try:
            os.lseek(self.fd, 0, os.SEEK_SET)
            return int(os.read(self.fd, 32).decode().strip())
        except (OSError, ValueError):
            return None

    def close(self) -> None:
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None

class PkgThrottleEngine(BaseEngine):
    def __init__(self, config_path: str = ""):
        self.domain = self.find_package_domain()
        self.energy_file = self.domain / "energy_uj" if self.domain else None
        self.reader = None
        self.last_e = None
        self.last_t = None
        self.max_energy = safe_read_int(self.domain / "max_energy_range_uj") or 0 if self.domain else 0
        if self.energy_file and self.energy_file.exists():
            import time
            self.reader = FastEnergyReader(self.energy_file)
            self.last_e = self.reader.read()
            self.last_t = time.perf_counter()

    def __del__(self) -> None:
        if hasattr(self, "reader") and self.reader:
            self.reader.close()

    def find_package_domain(self) -> Path | None:
        domains = list(RAPL_BASE.glob("*rapl*"))
        domains.sort(key=lambda p: (1 if "mmio" in p.name else 0, p.name))
        for d in domains:
            name_file = d / "name"
            if name_file.exists() and name_file.read_text().strip() == "package-0":
                if (d / "constraint_0_power_limit_uw").exists():
                    return d.resolve()
        return None

    @property
    def target_path(self) -> str:
        return str(self.domain) if self.domain else "/sys/class/powercap"

    def load_state(self) -> dict[str, Any]:
        state = {}
        if not self.domain:
            return state

        pl1 = safe_read_int(self.domain / "constraint_0_power_limit_uw")
        pl2 = safe_read_int(self.domain / "constraint_1_power_limit_uw")
        pl4 = safe_read_int(self.domain / "constraint_2_power_limit_uw")
        pl1_time = safe_read_int(self.domain / "constraint_0_time_window_us")
        pl2_time = safe_read_int(self.domain / "constraint_1_time_window_us")

        values = {}
        if pl1 is not None:
            values["pl1"] = pl1 // 1_000_000
        if pl2 is not None:
            values["pl2"] = pl2 // 1_000_000
        if pl4 is not None:
            values["pl4"] = pl4 // 1_000_000
        if pl1_time is not None:
            values["pl1_time"] = round(pl1_time / 1_000_000, 2)
        if pl2_time is not None:
            values["pl2_time"] = round(pl2_time / 1_000_000, 4)

        for k, v in values.items():
            state[k] = v
            state[f"DEFAULT/{k}"] = v

        return state

    def write_value(self, target_key: str, target_scope: str, new_value: str, item_type: str = "string") -> tuple[bool, str, str]:
        if not self.domain:
            return False, "No active RAPL domain found", ""

        mapping = {
            "pl1": "constraint_0_power_limit_uw",
            "pl2": "constraint_1_power_limit_uw",
            "pl4": "constraint_2_power_limit_uw",
            "pl1_time": "constraint_0_time_window_us",
            "pl2_time": "constraint_1_time_window_us",
        }

        sysfs_file = mapping.get(target_key)
        if not sysfs_file:
            return False, f"Unknown key: {target_key}", ""

        try:
            val_float = float(new_value)
        except ValueError:
            return False, f"Invalid value: {new_value}", ""

        if target_key in ("pl1", "pl2", "pl4"):
            val = int(val_float * 1_000_000)
        else:
            val = int(val_float * 1_000_000)

        # Write to system
        if not safe_write(self.domain / sysfs_file, val):
            return False, "Failed to write parameter (unsupported or permission denied)", ""

        # Verify write
        actual = safe_read_int(self.domain / sysfs_file)
        if actual is None:
            return False, "Write verification failed (file unreadable)", ""

        if actual == val:
            return True, f"Successfully set {target_key} to {new_value}", ""
        elif val != 0 and (abs(actual - val) / val) <= 0.05:
            if target_key in ("pl1_time", "pl2_time"):
                actual_display = f"{actual / 1_000_000:.2f}s"
            else:
                actual_display = f"{actual // 1_000_000} W"
            return True, f"Successfully set {target_key} to {new_value} (quantized to {actual_display})", ""
        else:
            if target_key in ("pl1_time", "pl2_time"):
                actual_display = f"{actual / 1_000_000:.2f}s"
            else:
                actual_display = f"{actual // 1_000_000} W"
            return False, f"Rejected by hardware! Locked at: {actual_display}", ""

    def get_telemetry(self) -> str:
        if not self.reader:
            return "Package Power Telemetry: N/A"

        import time
        curr_e = self.reader.read()
        curr_t = time.perf_counter()

        pkg_watts = 0.0
        if curr_e is not None and self.last_e is not None:
            delta_e = curr_e - self.last_e
            delta_t = curr_t - self.last_t
            if delta_t > 0:
                if delta_e < 0 and self.max_energy > 0:
                    delta_e += self.max_energy
                pkg_watts = (delta_e / 1_000_000) / delta_t

        self.last_e = curr_e
        self.last_t = curr_t

        # Build telemetry bar
        bar_w = 20
        pl2_raw = safe_read_int(self.domain / "constraint_1_power_limit_uw")
        pl2_w = pl2_raw // 1_000_000 if pl2_raw else 150
        dynamic_max = max(pl2_w, 100)

        filled = max(0, min(bar_w, int((pkg_watts / dynamic_max) * bar_w)))
        bar_graph = "█" * filled + "░" * (bar_w - filled)

        return f"⚡ Package: {pkg_watts:5.1f} W  [{bar_graph}]  Limit: {dynamic_max} W"
