from pathlib import Path

from browser_stealth.profiles.hygiene import clean_profile_cache


def test_clean_profile_cache(tmp_path: Path) -> None:
    profile_dir = tmp_path / "test_user_profile"
    profile_dir.mkdir(parents=True)

    # Создаем критические данные (не должны удаляться)
    cookies_file = profile_dir / "Default" / "Cookies"
    cookies_file.parent.mkdir(parents=True, exist_ok=True)
    cookies_file.write_text("critical_cookie_data", encoding="utf-8")

    prefs_file = profile_dir / "Default" / "Preferences"
    prefs_file.write_text("{}", encoding="utf-8")

    # Создаем кэш-файлы (должны удалиться)
    cache_dir = profile_dir / "Default" / "Cache" / "Cache_Data"
    cache_dir.mkdir(parents=True, exist_ok=True)
    file1 = cache_dir / "data_0"
    file1.write_bytes(b"x" * 1024)

    gpu_cache_dir = profile_dir / "Default" / "GPUCache"
    gpu_cache_dir.mkdir(parents=True, exist_ok=True)
    file2 = gpu_cache_dir / "data_gpu"
    file2.write_bytes(b"y" * 2048)

    freed = clean_profile_cache(profile_dir)
    assert freed == 1024 + 2048

    # Проверяем, что кэш удален
    assert not file1.exists()
    assert not file2.exists()

    # Проверяем, что куки и настройки сохранены!
    assert cookies_file.exists()
    assert cookies_file.read_text(encoding="utf-8") == "critical_cookie_data"
    assert prefs_file.exists()
