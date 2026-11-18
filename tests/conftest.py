import pytest

from extract_generator.build import build
from extract_generator.output import write_all


@pytest.fixture(scope="session")
def output_for(tmp_path_factory):
    """Write the full output once per seed and share it across tests."""
    written = {}

    def output(seed):
        if seed not in written:
            folder = tmp_path_factory.mktemp(f"seed{seed}")
            write_all(build(seed), folder)
            written[seed] = folder
        return written[seed]

    return output
