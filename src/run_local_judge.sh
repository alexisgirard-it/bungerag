#!/bin/zsh
# Juge Cerebras sur les reponses locales - boucle auto-reparante.
cd ~/BungeRAG
LOG=eval/cache/run-judge-ollama.log
echo "=== demarrage $(date) ===" >> $LOG
for i in $(seq 1 30); do
  if grep -q "etage B termine" $LOG; then break; fi
  echo "--- passe $i $(date) ---" >> $LOG
  LLM_BACKEND=ollama .venv/bin/python src/eval_ragas.py --judge >> $LOG 2>&1
  sleep 30
done
echo "=== DONE $(date) ===" >> $LOG
