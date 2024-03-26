from custodian.utils import tracked_lru_cache


def test_cache_and_clear():
    n_calls = 0

    @tracked_lru_cache
    def some_func(x):
        nonlocal n_calls
        n_calls += 1
        return x

    assert some_func(1) == 1
    assert n_calls == 1
    assert some_func(2) == 2
    assert n_calls == 2
    assert some_func(1) == 1
    assert n_calls == 2

    assert len(tracked_lru_cache.cached_functions) == 1

    tracked_lru_cache.tracked_cache_clear()

    assert len(tracked_lru_cache.cached_functions) == 0

    assert some_func(1) == 1
    assert n_calls == 3
