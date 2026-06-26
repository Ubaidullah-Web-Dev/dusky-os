#!/usr/bin/env python3
# =============================================================================
# Elite ZSTD Compression Ratio & Throughput Forensic Analyzer [V5 - C-FFI Bare Metal]
# Target: Arch Linux Cutting-Edge (Kernel 7.1+, Python 3.14+)
# =============================================================================

import os
import sys
import time
import ctypes
from ctypes import c_size_t, c_void_p, c_int, c_char_p, POINTER
from dataclasses import dataclass
from typing import NoReturn

if sys.version_info < (3, 14):
    sys.exit("FATAL: This architect-grade script requires Python 3.14+.")

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.align import Align
    from rich.prompt import IntPrompt
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
except ImportError:
    sys.exit("FATAL: 'rich' library missing. Run: pacman -S python-rich")

console = Console()

# =============================================================================
# Bare-Metal C-FFI Bindings to /usr/lib/libzstd.so
# =============================================================================
try:
    # Dynamically load the Arch Linux shared object library
    zstd = ctypes.CDLL("libzstd.so.1")
except OSError:
    sys.exit("[bold red]FATAL: libzstd.so.1 not found in library path. Ensure zstd is installed.[/bold red]")

# size_t ZSTD_compressBound(size_t srcSize);
zstd.ZSTD_compressBound.argtypes = [c_size_t]
zstd.ZSTD_compressBound.restype = c_size_t

# size_t ZSTD_compress(void* dst, size_t dstCapacity, const void* src, size_t srcSize, int compressionLevel);
zstd.ZSTD_compress.argtypes = [c_void_p, c_size_t, c_void_p, c_size_t, c_int]
zstd.ZSTD_compress.restype = c_size_t

# size_t ZSTD_decompress(void* dst, size_t dstCapacity, const void* src, size_t compressedSize);
zstd.ZSTD_decompress.argtypes = [c_void_p, c_size_t, c_void_p, c_size_t]
zstd.ZSTD_decompress.restype = c_size_t

# unsigned ZSTD_isError(size_t code);
zstd.ZSTD_isError.argtypes = [c_size_t]
zstd.ZSTD_isError.restype = c_int

# const char* ZSTD_getErrorName(size_t code);
zstd.ZSTD_getErrorName.argtypes = [c_size_t]
zstd.ZSTD_getErrorName.restype = c_char_p

def check_zstd_error(code: int, context: str) -> None:
    """Evaluates the return code from C against the ZSTD error macros."""
    if zstd.ZSTD_isError(code):
        err_msg = zstd.ZSTD_getErrorName(code).decode('utf-8')
        raise RuntimeError(f"ZSTD FFI Error during {context}: {err_msg}")

@dataclass(slots=True, kw_only=True)
class BenchmarkResult:
    level: int
    orig_size_mb: float
    compr_size_bytes: int
    comp_time_ns: int
    decomp_time_ns: int

    @property
    def ratio(self) -> float:
        return (self.orig_size_mb * 1024 * 1024) / max(self.compr_size_bytes, 1)

    @property
    def compr_size_mb(self) -> float:
        return self.compr_size_bytes / (1024 * 1024)

    @property
    def saved_mb(self) -> float:
        return self.orig_size_mb - self.compr_size_mb

    @property
    def comp_speed_mb_s(self) -> float:
        return self.orig_size_mb / (self.comp_time_ns / 1e9)

    @property
    def decomp_speed_mb_s(self) -> float:
        return self.orig_size_mb / (self.decomp_time_ns / 1e9)

def format_duration(nanoseconds: int) -> str:
    seconds = nanoseconds / 1e9
    if seconds < 1.0:
        return f"{seconds * 1000:.2f}ms"
    if seconds < 60.0:
        return f"{seconds:.2f}s"
    return f"{int(seconds // 60)}m {seconds % 60:.1f}s"

def generate_realistic_data(size_bytes: int) -> bytearray:
    """Pre-allocates the exact memory array for C-pointer injection."""
    console.print("[cyan][INFO][/cyan] Allocating contiguous heap blocks for FFI pointer mapping...")
    
    view = bytearray(size_bytes)
    base_text = (
        b'{"log_level":"INFO","timestamp":"2026-06-26T19:02:55Z","system":"arch_linux_core","kernel":"7.1.0-arch1-1",'
        b'"event":"memory_compaction","metrics":{"cpu":14.5,"mem_free":1024,"zram_active":true,"throughput_mb":1350.5}} '
        b'Arch Linux rolling release. Memory compression is a critical facet of modern system architectures. '
    )
    base_len = len(base_text)
    offset = 0
    chunk_size = 1024 * 1024
    
    while offset < size_bytes:
        current_chunk = min(chunk_size, size_bytes - offset)
        rand_len = int(current_chunk * 0.33)
        text_len = current_chunk - rand_len
        
        view[offset : offset + rand_len] = os.urandom(rand_len)
        offset += rand_len
        
        repeats = (text_len // base_len) + 1
        view[offset : offset + text_len] = (base_text * repeats)[:text_len]
        offset += text_len
        
    return view

def benchmark_ffi(src_data: bytearray, level: int) -> BenchmarkResult:
    """Executes compression algorithm directly in system RAM via C pointers."""
    src_size = len(src_data)
    
    # 1. Ask C-library for maximum possible output buffer size
    dst_capacity = zstd.ZSTD_compressBound(src_size)
    dst_data = bytearray(dst_capacity)
    
    # Extract raw memory pointers for the C context
    src_ptr = (ctypes.c_char * src_size).from_buffer(src_data)
    dst_ptr = (ctypes.c_char * dst_capacity).from_buffer(dst_data)
    
    # 2. FFI Compression
    t_start = time.perf_counter_ns()
    compressed_size = zstd.ZSTD_compress(dst_ptr, dst_capacity, src_ptr, src_size, level)
    comp_time_ns = max(time.perf_counter_ns() - t_start, 1)
    
    check_zstd_error(compressed_size, "Compression")
    
    # Trim the output buffer to the exact compressed size
    compressed_payload = bytearray(compressed_size)
    ctypes.memmove((ctypes.c_char * compressed_size).from_buffer(compressed_payload), dst_ptr, compressed_size)
    
    # 3. FFI Decompression
    decomp_dst_data = bytearray(src_size) # We know exact original size
    comp_src_ptr = (ctypes.c_char * compressed_size).from_buffer(compressed_payload)
    decomp_dst_ptr = (ctypes.c_char * src_size).from_buffer(decomp_dst_data)
    
    t_start = time.perf_counter_ns()
    decomp_size = zstd.ZSTD_decompress(decomp_dst_ptr, src_size, comp_src_ptr, compressed_size)
    decomp_time_ns = max(time.perf_counter_ns() - t_start, 1)
    
    check_zstd_error(decomp_size, "Decompression")

    return BenchmarkResult(
        level=level,
        orig_size_mb=src_size / (1024 * 1024),
        compr_size_bytes=compressed_size,
        comp_time_ns=comp_time_ns,
        decomp_time_ns=decomp_time_ns
    )

def main() -> NoReturn | None:
    header = Panel(
        Align.center(
            "[bold cyan]⚡ ZSTD Multi-Level Compression & Throughput Forensic Analyzer ⚡[/bold cyan]\n"
            "[dim]Targeting Arch Linux | Peak Bare-Metal Execution via C-FFI (Foreign Function Interface)[/dim]"
        ),
        border_style="magenta",
        padding=(1, 2)
    )
    console.print(header)
    
    while True:
        max_level = IntPrompt.ask("\nEnter maximum ZSTD compression level (1-22)", default=10)
        if 1 <= max_level <= 22:
            break
        console.print("[bold red]Invalid level.[/bold red]")
    
    size_mb = IntPrompt.ask("Enter test data payload size (in Megabytes)", default=50)
    if size_mb <= 0:
        sys.exit("[bold red]FATAL: Size must be a positive integer.[/bold red]")
        
    size_bytes = size_mb * 1024 * 1024
    data = generate_realistic_data(size_bytes)
    
    results: list[BenchmarkResult] = []
    
    with Progress(
        SpinnerColumn(style="bold cyan"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(complete_style="cyan", finished_style="green"),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console
    ) as progress:
        task = progress.add_task("[cyan]Benchmarking C-Library...[/cyan]", total=max_level)
        
        for level in range(1, max_level + 1):
            progress.update(task, description=f"[cyan]Analyzing Level {level}...[/cyan]")
            try:
                results.append(benchmark_ffi(data, level))
            except Exception as e:
                console.print(f"\n[bold red]Critical FFI Error at level {level}: {e}[/bold red]")
            progress.advance(task)
            
    table = Table(
        title=f"\n📊 ZSTD Bare-Metal Performance Matrix ({size_mb}MB Mixed-Entropy Payload)",
        title_style="bold magenta",
        header_style="bold cyan",
        border_style="dim blue",
        expand=True
    )
    
    table.add_column("Level", justify="center", style="bold yellow")
    table.add_column("Compressed", justify="right", style="white")
    table.add_column("Ratio", justify="right", style="bold green")
    table.add_column("Space Saved", justify="right", style="white")
    table.add_column("C-API Compression", justify="right", style="cyan")
    table.add_column("C-API Decompression", justify="right", style="magenta")
    
    for r in results:
        table.add_row(
            str(r.level),
            f"{r.compr_size_mb:.2f} MB",
            f"{r.ratio:.2f}x",
            f"{r.saved_mb:.2f} MB",
            f"{format_duration(r.comp_time_ns)} ({r.comp_speed_mb_s:.1f} MB/s)",
            f"{format_duration(r.decomp_time_ns)} ({r.decomp_speed_mb_s:.1f} MB/s)"
        )
        
    console.print(table)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\n[bold yellow]SIGINT caught — operation aborted.[/bold yellow]")
