"""
하이브리드 시스템 자원 모니터링 모듈.

psutil + PyTorch 이중 방어선:
  GPU(CUDA/MPS) 있음 → VRAM 사용
  CPU 전용         → 가용 RAM * 0.6 (안전 마진)

예외 처리:
- psutil 실패 → 보수적 기본값 사용
- torch.cuda 실패 → GPU 없음으로 처리
- sysctl 실패 → 8GB 기본값 사용
모든 감지 오류가 앱 시작을 막지 않는다.
"""
from __future__ import annotations

import platform
import subprocess
from functools import lru_cache

import psutil
import torch

_CPU_RAM_SAFETY_FACTOR = 0.60  # 가용 RAM 중 모델에 할당할 최대 비율


@lru_cache(maxsize=1)
def detect() -> tuple[str, float, str]:
    """
    OS·유효 메모리(GB)·연산 모드를 반환한다. lru_cache로 1회 캐시.

    Returns:
        (os_name, effective_gb, compute_mode)
        compute_mode: "cuda" | "mps" | "cpu"
    """
    system = platform.system()

    # ── NVIDIA GPU (CUDA) ─────────────────────────────────────────────────
    try:
        if torch.cuda.is_available():
            vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
            return system, vram_gb, "cuda"
    except Exception:
        pass  # CUDA 감지 실패 → 다음 단계로

    # ── Apple Silicon (MPS / 통합 메모리) ────────────────────────────────
    if system == "Darwin":
        try:
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True, text=True, timeout=5
            )
            mem_gb = int(result.stdout.strip()) / (1024 ** 3)
            return system, mem_gb, "mps"
        except Exception:
            return system, 8.0, "mps"  # 감지 실패 시 8GB 기본값

    # ── CPU 전용 (GPU 없는 Linux / Windows) ──────────────────────────────
    try:
        available_gb = psutil.virtual_memory().available / (1024 ** 3)
        budget_gb    = max(available_gb * _CPU_RAM_SAFETY_FACTOR, 1.0)
        return system, budget_gb, "cpu"
    except Exception:
        return system, 2.0, "cpu"  # psutil 실패 시 초소형 모델 선택


def get_live_stats() -> dict:
    """
    실시간 CPU·RAM·GPU 현황을 반환한다 (캐시 없음).

    모든 감지 항목을 개별 try-except로 격리하므로
    일부 항목 실패 시에도 나머지 항목은 정상 반환된다.

    Returns:
        cpu_percent, ram_total_gb, ram_used_gb, ram_available_gb,
        ram_percent, gpu_name, gpu_vram_total_gb, gpu_vram_free_gb
    """
    stats: dict = {
        "cpu_percent":       0.0,
        "ram_total_gb":      0.0,
        "ram_used_gb":       0.0,
        "ram_available_gb":  0.0,
        "ram_percent":       0.0,
        "gpu_name":          "",
        "gpu_vram_total_gb": 0.0,
        "gpu_vram_free_gb":  0.0,
    }

    try:
        stats["cpu_percent"] = psutil.cpu_percent(interval=0.2)
    except Exception:
        pass

    try:
        mem = psutil.virtual_memory()
        stats["ram_total_gb"]     = mem.total     / (1024 ** 3)
        stats["ram_used_gb"]      = mem.used       / (1024 ** 3)
        stats["ram_available_gb"] = mem.available  / (1024 ** 3)
        stats["ram_percent"]      = mem.percent
    except Exception:
        pass

    try:
        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            free, total = torch.cuda.mem_get_info(0)
            stats["gpu_name"]          = props.name
            stats["gpu_vram_total_gb"] = total / (1024 ** 3)
            stats["gpu_vram_free_gb"]  = free  / (1024 ** 3)
    except Exception:
        pass

    return stats
