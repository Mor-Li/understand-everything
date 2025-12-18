from contextlib import contextmanager
from collections import defaultdict
import torch


class CUDATimer:

    def __init__(self):
        self.events = defaultdict(list)

    @contextmanager
    def record(self, name, enabled=True):
        if not enabled:
            yield
        else:
            start, end = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
            self.events[name].append((start, end))
            start.record()
            yield
            end.record()

    def log(self):
        torch.cuda.synchronize()
        ret = []
        for name, events in self.events.items():
            total = 0
            count = len(self.events)
            for start, end in events:
                total += start.elapsed_time(end)
            ret.append(f"{name} {total:.2f}ms/{count}times")
        return ", ".join(ret)
