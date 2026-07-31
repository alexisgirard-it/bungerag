#!/bin/zsh
# Extension (c) : reponses avec fenetrage (bras -window), auto-reparant.
cd ~/BungeRAG
LOG=eval/cache/run-window.log
echo "=== demarrage $(date) ===" >> $LOG
for i in $(seq 1 20); do
  n=$(.venv/bin/python -c "import json;print(len(json.load(open('eval/cache/answers-window.json'))))" 2>/dev/null || echo 0)
  if [ "$n" = "40" ]; then echo "=== WINDONE $(date) ===" >> $LOG; exit 0; fi
  echo "--- passe $i (cache: $n/40) $(date) ---" >> $LOG
  RAG_WINDOW=1 EVAL_SUFFIX=-window .venv/bin/python src/eval_ragas.py --answers >> $LOG 2>&1
  sleep 20
done
