"""config/ 모듈 테스트 — settings, models, env."""
import pytest


class TestSettings:
    def test_summary_styles_ko_has_four_styles(self):
        from config.settings import get_styles
        styles = get_styles("ko")
        assert len(styles) == 4

    def test_summary_styles_en_has_four_styles(self):
        from config.settings import get_styles
        styles = get_styles("en")
        assert len(styles) == 4

    def test_get_default_style_ko(self):
        from config.settings import get_default_style
        assert get_default_style("ko") == "간결 요약"

    def test_get_default_style_en(self):
        from config.settings import get_default_style
        assert get_default_style("en") == "Concise"

    def test_presets_ko_has_custom_slot(self):
        from config.settings import get_presets
        presets = get_presets("ko")
        assert "사용자 지정" in presets
        assert presets["사용자 지정"] == ""

    def test_presets_en_has_custom_slot(self):
        from config.settings import get_presets
        presets = get_presets("en")
        assert "Custom" in presets
        assert presets["Custom"] == ""

    def test_get_default_preset_ko(self):
        from config.settings import get_default_preset
        assert get_default_preset("ko") == "요약 전문가"

    def test_get_default_preset_en(self):
        from config.settings import get_default_preset
        assert get_default_preset("en") == "Summarizer"

    def test_suggested_models_is_list(self):
        from config.settings import SUGGESTED_MODELS
        assert isinstance(SUGGESTED_MODELS, list)
        assert len(SUGGESTED_MODELS) > 0

    def test_chunk_size_positive(self):
        from config.settings import CHUNK_SIZE
        assert CHUNK_SIZE > 0


class TestModels:
    def test_model_for_vram_cuda_large(self):
        from config.models import model_for_vram
        assert model_for_vram(24.0) == "gemma3:12b"

    def test_model_for_vram_mid(self):
        from config.models import model_for_vram
        assert model_for_vram(10.0) == "gemma3:4b"

    def test_model_for_vram_small(self):
        from config.models import model_for_vram
        assert model_for_vram(4.0) == "gemma3:1b"

    def test_model_for_vram_cpu_only(self):
        from config.models import model_for_vram
        assert model_for_vram(0.0) == "gemma3:1b"

    def test_model_for_vram_negative_is_minimum(self):
        from config.models import model_for_vram
        assert model_for_vram(-1.0) == "gemma3:1b"

    def test_get_installed_models_returns_list(self):
        from config.models import get_installed_models, refresh_installed_models
        refresh_installed_models()
        models = get_installed_models()
        assert isinstance(models, list)

    def test_refresh_clears_cache(self):
        from config.models import get_installed_models, refresh_installed_models
        first  = get_installed_models()
        refresh_installed_models()
        second = get_installed_models()
        assert first == second  # 내용은 같아야 함 (캐시 갱신 후 같은 결과)


class TestEnv:
    def test_ollama_host_has_default(self):
        from config.env import OLLAMA_HOST
        assert OLLAMA_HOST
        assert "http" in OLLAMA_HOST

    def test_whisper_model_has_valid_size(self):
        from config.env import WHISPER_MODEL
        valid = {"tiny", "base", "small", "medium", "large"}
        assert WHISPER_MODEL in valid

    def test_export_dir_is_string(self):
        from config.env import EXPORT_DIR
        assert isinstance(EXPORT_DIR, str)
