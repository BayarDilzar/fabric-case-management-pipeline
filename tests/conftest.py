import pytest

from extract_generator.build import build
from extract_generator.output import write_all


@pytest.fixture(scope="session")
def built(tmp_path_factory):
    """Build and write the full output once per seed; return the extracts and the folder."""
    cache = {}

    def get(seed):
        if seed not in cache:
            folder = tmp_path_factory.mktemp(f"seed{seed}")
            extracts = build(seed)
            write_all(extracts, seed, folder)
            cache[seed] = (extracts, folder)
        return cache[seed]

    return get


@pytest.fixture(scope="session")
def output_for(built):
    return lambda seed: built(seed)[1]
