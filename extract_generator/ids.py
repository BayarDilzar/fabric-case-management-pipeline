HELD_BACK = 50


class IdAllocator:
    """Issues ids in creation order, never issuing the held-back numbers.

    Orphan defects point at held-back ids, so the orphans look like normal ids
    and no later extract can create the missing parent by accident.
    """

    def __init__(self, prefix, rng, history_count):
        self.prefix = prefix
        span = range(1, history_count + HELD_BACK + 1)
        held = sorted(rng.sample(span, HELD_BACK))
        self.held_back = [self._format(number) for number in held]
        held_numbers = set(held)
        self._history = [number for number in span if number not in held_numbers]
        self._next = history_count + HELD_BACK + 1

    def _format(self, number):
        return f"{self.prefix}{number:06d}"

    def history_ids(self):
        return [self._format(number) for number in self._history]

    def new_id(self):
        value = self._format(self._next)
        self._next += 1
        return value
