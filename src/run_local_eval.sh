#!/bin/zsh
# Runner auto-réparant du profil public_v1 avec tous les appels via Ollama.
ROOT=${0:A:h:h}
cd "$ROOT"
LOG=eval/cache/run-ollama.log
echo "=== démarrage $(date) ===" >> "$LOG"
for i in $(seq 1 60); do
  STATUS=$(LLM_BACKEND=ollama EVAL_PROFILE=public_v1 \
    .venv/bin/python src/eval_ragas.py --status)
  ANSWERS=$(print -r -- "$STATUS" | .venv/bin/python -c \
    'import json,sys; d=json.load(sys.stdin); print(f"{d[\"answers\"]}/{d[\"answers_expected\"]}")')
  if [ "${ANSWERS%/*}" = "${ANSWERS#*/}" ]; then
    echo "=== FULLDONE $ANSWERS réponses $(date) ===" >> "$LOG"
    exit 0
  fi
  echo "--- passe $i (cache: $ANSWERS) $(date) ---" >> "$LOG"
  LLM_BACKEND=ollama EVAL_PROFILE=public_v1 RERANK_BATCH=4 \
    .venv/bin/python src/eval_ragas.py --answers >> "$LOG" 2>&1
  sleep 15
done
echo "=== INCOMPLET $(date) ===" >> "$LOG"
exit 1
