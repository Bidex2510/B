from trading.watchlist import ManualWatchlist


def test_add_returns_true_and_persists(tmp_path):
    path = tmp_path / "manual_watchlist.json"
    watchlist = ManualWatchlist(path)
    assert watchlist.add("abcd") is True
    assert watchlist.list() == ["ABCD"]
    assert ManualWatchlist(path).list() == ["ABCD"]


def test_add_duplicate_returns_false(tmp_path):
    path = tmp_path / "manual_watchlist.json"
    watchlist = ManualWatchlist(path)
    watchlist.add("ABCD")
    assert watchlist.add("abcd") is False
    assert watchlist.list() == ["ABCD"]


def test_remove_existing_returns_true(tmp_path):
    path = tmp_path / "manual_watchlist.json"
    watchlist = ManualWatchlist(path)
    watchlist.add("ABCD")
    assert watchlist.remove("abcd") is True
    assert watchlist.list() == []


def test_remove_missing_returns_false(tmp_path):
    path = tmp_path / "manual_watchlist.json"
    watchlist = ManualWatchlist(path)
    assert watchlist.remove("ABCD") is False


def test_add_empty_symbol_raises(tmp_path):
    path = tmp_path / "manual_watchlist.json"
    watchlist = ManualWatchlist(path)
    try:
        watchlist.add("   ")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_missing_file_starts_empty(tmp_path):
    path = tmp_path / "does_not_exist.json"
    assert ManualWatchlist(path).list() == []
