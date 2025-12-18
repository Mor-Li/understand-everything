import torch
from torch import nn


class Sampler(nn.Module):

    def __init__(self):
        super().__init__()

    def forward(self, logits: torch.Tensor, temperatures: torch.Tensor | None = None):
        logits = logits.to(torch.float)
        if temperatures is not None:
            logits.div_(temperatures.unsqueeze(dim=1))
        probs = torch.softmax(logits, dim=-1, dtype=torch.float)
        # logprobs = torch.log_softmax(logits, dim=-1, dtype=torch.float)
        sampled_tokens = probs.div_(torch.empty_like(probs).exponential_(1)).argmax(dim=-1)
        return sampled_tokens
