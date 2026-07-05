"""Reranker Qwen3-0.6B - le second regard, plus lent mais plus fin.

Difference avec l'embedding (bi-encodeur) : ici le modele lit la question ET
le document ENSEMBLE (cross-encodeur) et repond litteralement "yes"/"no" a
"ce document repond-il a la question ?". Le score = probabilite du "yes".
C'est plus precis (le modele voit les interactions mot a mot) mais lineaire
en nombre de documents -> on ne l'applique qu'aux 20-40 candidats du
retrieval, jamais au corpus entier.
"""

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL = "Qwen/Qwen3-Reranker-0.6B"
INSTRUCTION = ("Given a question about Mario Bunge's philosophy, judge whether "
               "the passage answers it")

# gabarit impose par le model card Qwen3-Reranker
PREFIX = ('<|im_start|>system\nJudge whether the Document meets the requirements '
          'based on the Query and the Instruct provided. Note that the answer '
          'can only be "yes" or "no".<|im_end|>\n<|im_start|>user\n')
SUFFIX = '<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'

class Reranker:
    def __init__(self, device="mps"):
        self.tok = AutoTokenizer.from_pretrained(MODEL, padding_side="left")
        self.model = (AutoModelForCausalLM
                      .from_pretrained(MODEL, dtype=torch.float16)
                      .to(device).eval())
        self.device = device
        self.yes = self.tok.convert_tokens_to_ids("yes")
        self.no = self.tok.convert_tokens_to_ids("no")

    def score(self, query, docs, batch_size=8):
        """Probabilite P(yes) pour chaque (query, doc)."""
        prompts = [f"{PREFIX}<Instruct>: {INSTRUCTION}\n<Query>: {query}\n"
                   f"<Document>: {d}{SUFFIX}" for d in docs]
        scores = []
        with torch.no_grad():
            for i in range(0, len(prompts), batch_size):
                enc = self.tok(prompts[i:i + batch_size], padding=True,
                               truncation=True, max_length=1024,
                               return_tensors="pt").to(self.device)
                logits = self.model(**enc).logits[:, -1, :]
                pair = logits[:, [self.no, self.yes]].float().log_softmax(dim=1)
                scores.extend(pair[:, 1].exp().tolist())
        return scores
