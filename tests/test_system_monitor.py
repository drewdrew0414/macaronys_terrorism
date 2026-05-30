"""src/utils/system_monitor.py 테스트."""
import pytest
from unittest.mock import patch, MagicMock


class TestDetect:
    def setup_method(self):
        """각 테스트 전에 lru_cache를 초기화한다."""
        from src.utils.system_monitor import detect
        detect.cache_clear()

    def test_returns_three_tuple(self):
        from src.utils.system_monitor import detect
        result = detect()
        assert len(result) == 3
        os_name, effective_gb, compute_mode = result
        assert isinstance(os_name, str)
        assert isinstance(effective_gb, float)
        assert effective_gb > 0
        assert compute_mode in ("cuda", "mps", "cpu")

    def test_cuda_mode_uses_vram(self):
        from src.utils.system_monitor import detect
        detect.cache_clear()

        mock_props = MagicMock()
        mock_props.total_memory = 8 * 1024 ** 3  # 8GB

        with patch("torch.cuda.is_available", return_value=True):
            with patch("torch.cuda.get_device_properties", return_value=mock_props):
                os_name, vram_gb, mode = detect()

        assert mode == "cuda"
        assert abs(vram_gb - 8.0) < 0.1

    def test_cpu_mode_uses_ram_budget(self):
        from src.utils.system_monitor import detect
        detect.cache_clear()

        mock_mem = MagicMock()
        mock_mem.available = 10 * 1024 ** 3  # 10GB available

        with patch("torch.cuda.is_available", return_value=False):
            with patch("platform.system", return_value="Linux"):
                with patch("psutil.virtual_memory", return_value=mock_mem):
                    os_name, budget_gb, mode = detect()

        assert mode == "cpu"
        # 안전 마진 60% 적용: 10GB * 0.6 = 6GB
        assert abs(budget_gb - 6.0) < 0.1

    def test_darwin_uses_hw_memsize(self):
        from src.utils.system_monitor import detect
        detect.cache_clear()

        with patch("torch.cuda.is_available", return_value=False):
            with patch("platform.system", return_value="Darwin"):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value.stdout = str(16 * 1024 ** 3)
                    os_name, mem_gb, mode = detect()

        assert mode == "mps"
        assert abs(mem_gb - 16.0) < 0.1

    def test_sysctl_failure_uses_default(self):
        from src.utils.system_monitor import detect
        detect.cache_clear()

        with patch("torch.cuda.is_available", return_value=False):
            with patch("platform.system", return_value="Darwin"):
                with patch("subprocess.run", side_effect=Exception("sysctl 실패")):
                    os_name, mem_gb, mode = detect()

        assert mode == "mps"
        assert mem_gb == 8.0  # 기본값

    def test_psutil_failure_uses_default(self):
        from src.utils.system_monitor import detect
        detect.cache_clear()

        with patch("torch.cuda.is_available", return_value=False):
            with patch("platform.system", return_value="Linux"):
                with patch("psutil.virtual_memory", side_effect=Exception("psutil 오류")):
                    os_name, budget_gb, mode = detect()

        assert mode == "cpu"
        assert budget_gb == 2.0  # 기본값


class TestGetLiveStats:
    def test_returns_required_keys(self):
        from src.utils.system_monitor import get_live_stats
        stats = get_live_stats()
        required = [
            "cpu_percent", "ram_total_gb", "ram_used_gb",
            "ram_available_gb", "ram_percent",
            "gpu_name", "gpu_vram_total_gb", "gpu_vram_free_gb",
        ]
        for key in required:
            assert key in stats, f"키 누락: {key}"

    def test_cpu_percent_in_valid_range(self):
        from src.utils.system_monitor import get_live_stats
        stats = get_live_stats()
        assert 0 <= stats["cpu_percent"] <= 100

    def test_ram_values_non_negative(self):
        from src.utils.system_monitor import get_live_stats
        stats = get_live_stats()
        assert stats["ram_total_gb"] >= 0
        assert stats["ram_used_gb"] >= 0
        assert stats["ram_available_gb"] >= 0

    def test_psutil_failure_returns_zero_values(self):
        from src.utils.system_monitor import get_live_stats
        with patch("psutil.cpu_percent", side_effect=Exception("오류")):
            with patch("psutil.virtual_memory", side_effect=Exception("오류")):
                with patch("torch.cuda.is_available", return_value=False):
                    stats = get_live_stats()
        assert stats["cpu_percent"] == 0.0
        assert stats["ram_total_gb"] == 0.0
