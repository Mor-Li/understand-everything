import os
import subprocess
import torch


def get_gpu_memory(device_id: int = 0):
    torch.cuda.synchronize()
    result = subprocess.check_output(
        ['nvidia-smi', '-i', str(device_id), '--query-gpu=memory.total,memory.used,memory.free', '--format=csv,nounits,noheader'],
        encoding='utf-8'
    )
    total_memory, used_memory, free_memory = [int(x) for x in result.strip().split(', ')]
    return total_memory, used_memory, free_memory
    