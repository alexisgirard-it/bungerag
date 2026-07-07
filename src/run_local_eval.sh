#!/bin/zsh
# Runner auto-reparant pour l'eval locale (phase 8).
# Detache de toute session ; si le process python meurt (OOM, kill,
# veille...), la boucle le relance et le cache reprend ou il en etait.
cd ~/BungeRAG
LOG=eval/cache/run-ollama.log
echo "=== demarrage $(date) ===" >> $LOG
for i in $(seq 1 60); do
  n=$(.venv/bin/python -c "import json;print(len(json.load(open('eval/cache/answers-ollama.json'))))" 2>/dev/null || echo 0)
  if [ "$n" = "40" ]; then break; fi
  echo "--- passe $i (cache: $n/40) $(date) ---" >> $LOG
  LLM_BACKEND=ollama RERANK_BATCH=4 .venv/bin/python src/eval_ragas.py --answers >> $LOG 2>&1
  sleep 15
done
echo "=== DONE $(date) ===" >> $LOG
