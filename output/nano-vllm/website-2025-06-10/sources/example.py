import os
from nanovllm import LLM, SamplingParams
from transformers import AutoTokenizer


path = os.path.expanduser("~/huggingface/Qwen3-0.6B/")
tokenizer = AutoTokenizer.from_pretrained(path)
llm = LLM(path, enforce_eager=True)

sampling_params = SamplingParams(temperature=0.6, max_tokens=256)
prompts = [
    "自我介绍一下吧！",
    "列出100内所有素数",
]
prompts = [
    tokenizer.apply_chat_template(
        [{"role": "user", "content": prompt}],
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=True
    )
    for prompt in prompts
]
completions = llm.generate(prompts, sampling_params)

for p, c in zip(prompts, completions):
    print("\n\n")
    print(f"Prompt: {p}")
    print(f"Completion: {c}")
