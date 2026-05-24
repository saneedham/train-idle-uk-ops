from __future__ import annotations

from train_idle.save import load_game, new_game, save_game


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / 'save.json'

    state = new_game()
    state.money = 1234.5
    state.home = 'EXD'

    save_game(state, path=str(path))
    loaded = load_game(path=str(path))

    assert loaded is not None
    assert loaded.money == 1234.5
    assert loaded.home == 'EXD'
    assert loaded.region_ids_loaded  # should include default region
