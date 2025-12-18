from collections import defaultdict
from tqdm.auto import tqdm
from transformers import AutoConfig, AutoTokenizer

from nanovllm.config import Config
from nanovllm.sampling_params import SamplingParams
from nanovllm.engine.sequence import Sequence
from nanovllm.engine.scheduler import Scheduler
from nanovllm.engine.model_runner import ModelRunner


class LLMEngine:

    def __init__(self, model, **kwargs):
        config = Config(model)
        for k, v in kwargs.items():
            if hasattr(config, k):
                setattr(config, k, v)
        config.hf_config = AutoConfig.from_pretrained(config.model)
        config.max_model_len = min(config.max_model_len, config.hf_config.max_position_embeddings)
        self.tokenizer = AutoTokenizer.from_pretrained(config.model, use_fast=True)
        config.eos = self.tokenizer.eos_token_id
        self.model_runner = ModelRunner(config)
        self.scheduler = Scheduler(config)

    def add_request(self, prompt: str | list[int], sampling_params: SamplingParams):
        if isinstance(prompt, str):
            prompt = self.tokenizer.encode(prompt)
        seq = Sequence(prompt, sampling_params)
        self.scheduler.add(seq)

    def step(self):
        seqs, is_prefill = self.scheduler.schedule()
        token_ids = self.model_runner.run(seqs, is_prefill)
        finished = self.scheduler.postprocess(seqs, token_ids)
        return [(seq.seq_id, token_id, finish) for seq, token_id, finish in zip(seqs, token_ids, finished)]

    def is_finished(self):
        return self.scheduler.is_finished()

    def generate(
        self,
        prompts: list[str] | list[list[int]],
        sampling_params: SamplingParams | list[SamplingParams],
        use_tqdm: bool = True,
    ) -> list[str]:
        if use_tqdm:
            pbar = tqdm(total=len(prompts),
                desc="Processed prompts",
            )
        if not isinstance(SamplingParams, list):
            sampling_params = [sampling_params] * len(prompts)
        for prompt, sp in zip(prompts, sampling_params):
            self.add_request(prompt, sp)
        outputs = defaultdict(list)
        while not self.is_finished():
            output = self.step()
            for seq_id, token_id, finish in output:
                outputs[seq_id].append(token_id)
                if use_tqdm and finish:
                    pbar.update(1)
        outputs = [outputs[seq_id] for seq_id in sorted(outputs)]
        outputs = [self.tokenizer.decode(token_ids) for token_ids in outputs]
        if use_tqdm:
            pbar.close()
        return outputs
