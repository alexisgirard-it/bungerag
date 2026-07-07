#!/bin/zsh
# Complete les notes juge au rythme du quota Cerebras (fenetre glissante).
cd ~/BungeRAG
LOG=eval/cache/run-judge-trickle.log
for i in $(seq 1 48); do
  MISSING=$(.venv/bin/python -c "
import json
so = json.loads(open('eval/cache/ragas-scores-ollama.json').read())
q = {str(__import__('json').loads(l)['id']): __import__('json').loads(l) for l in open('eval/questions-eval.jsonl')}
c = [k for k in q if q[k]['type'] == 'contenu']
print(sum(1 for k in c for m in ('faithfulness','context_precision','context_recall')
          if k not in so or so[k].get(m) is None))")
  echo "--- passe $i : $MISSING notes manquantes $(date) ---" >> $LOG
  if [ "$MISSING" = "0" ]; then echo "=== FULLDONE $(date) ===" >> $LOG; exit 0; fi
  .venv/bin/python -c "
import json
p = 'eval/cache/ragas-scores-ollama.json'
s = json.loads(open(p).read())
for k in s:
    for m in list(s[k]):
        if s[k][m] is None: del s[k][m]
open(p,'w').write(json.dumps(s))"
  LLM_BACKEND=ollama .venv/bin/python src/eval_ragas.py --judge >> $LOG 2>&1
  sleep 1800
done
