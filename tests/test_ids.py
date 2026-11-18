import re
from random import Random

from extract_generator.ids import IdAllocator


def test_held_back_ids_are_never_issued_in_history_or_later():
    allocator = IdAllocator("C", Random(1), history_count=100)

    issued = allocator.history_ids() + [allocator.new_id() for _ in range(200)]

    assert len(allocator.held_back) == 50
    assert len(set(issued)) == 300
    assert not set(allocator.held_back) & set(issued)


def test_history_ids_are_sequential_and_new_ids_start_after_the_held_back_range():
    allocator = IdAllocator("E", Random(7), history_count=100)

    history = allocator.history_ids()

    assert len(history) == 100
    assert history == sorted(history)
    assert all(re.fullmatch(r"E\d{6}", value) for value in history)
    assert max(allocator.held_back) <= "E000150"
    assert allocator.new_id() == "E000151"
    assert allocator.new_id() == "E000152"
