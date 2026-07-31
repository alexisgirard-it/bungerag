#!/bin/zsh
# Complete les notes juge au rythme du quota Cerebras (fenetre glissante).
cd ~/BungeRAG
LOG=eval/cache/run-judge-trickle.log
for i in $(seq 1 48); do
  MISSING=$(.venv/bin/python -c "
import json
import os
so = json.loads(open('eval/cache/ragas-scores-ollama.json').read())
sg = json.loads(open('eval/cache/ragas-scores.json').read())
sw = json.loads(open('eval/cache/ragas-scores-window.json').read()) if os.path.exists('eval/cache/ragas-scores-window.json') else None
q = {str(__import__('json').loads(l)['id']): __import__('json').loads(l) for l in open('eval/questions-eval.jsonl')}
c = [k for k in q if q[k]['type'] == 'contenu']
arms = [x for x in (so, sg, sw) if x is not None]
print(sum(1 for s in arms for k in c for m in ('faithfulness','context_precision','context_recall')
          if k not in s or s[k].get(m) is None))")
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
  .venv/bin/python src/eval_ragas.py --judge >> $LOG 2>&1
  # bras fenetre : seulement quand ses 40 reponses existent
  W=$(.venv/bin/python -c "import json;print(len(json.load(open('eval/cache/answers-window.json'))))" 2>/dev/null || echo 0)
  [ "$W" = "40" ] && EVAL_SUFFIX=-window .venv/bin/python src/eval_ragas.py --judge >> $LOG 2>&1
  sleep 1800
done
