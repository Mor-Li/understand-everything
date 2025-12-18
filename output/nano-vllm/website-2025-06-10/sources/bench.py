import os
import time
import torch
from nanovllm import LLM, SamplingParams


batch_size = 256
seq_len = 1024
max_tokens = 512

path = os.path.expanduser("~/huggingface/Qwen3-0.6B/")
llm = LLM(path, enforce_eager=False)

prompt_token_ids = torch.randint(0, 10240, (batch_size, seq_len)).tolist()
sampling_params = SamplingParams(temperature=0.6, ignore_eos=True, max_tokens=max_tokens)

t = time.time()
completions = llm.generate(prompt_token_ids, sampling_params)
troughput = batch_size * max_tokens / (time.time() - t)
print(f"Throughput: {troughput: .2f}")
