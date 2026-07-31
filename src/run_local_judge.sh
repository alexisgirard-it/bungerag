#!/bin/zsh
# Juge Cerebras sur les reponses locales - boucle auto-reparante.
ROOT=${0:A:h:h}
cd "$ROOT"
LOG=eval/cache/run-judge-ollama.log
echo "=== demarrage $(date) ===" >> $LOG
for i in $(seq 1 30); do
  STATUS=$(LLM_BACKEND=ollama EVAL_PROFILE=public_v1 \
    .venv/bin/python src/eval_ragas.py --status)
  ANSWERS=$(print -r -- "$STATUS" | .venv/bin/python -c \
    'import json,sys; d=json.load(sys.stdin); print(f"{d[\"answers\"]}/{d[\"answers_expected\"]}")')
  NOTES=$(print -r -- "$STATUS" | .venv/bin/python -c \
    'import json,sys; d=json.load(sys.stdin); print(f"{d[\"notes\"]}/{d[\"notes_expected\"]}")')
  if [ "${ANSWERS%/*}" != "${ANSWERS#*/}" ]; then
    echo "=== ERREUR réponses incomplètes : $ANSWERS ===" >> "$LOG"
    exit 2
  fi
  if [ "${NOTES%/*}" = "${NOTES#*/}" ]; then
    echo "=== FULLDONE $ANSWERS réponses, $NOTES notes $(date) ===" >> "$LOG"
    exit 0
  fi
  echo "--- passe $i $(date) ---" >> $LOG
  LLM_BACKEND=ollama EVAL_PROFILE=public_v1 \
    .venv/bin/python src/eval_ragas.py --judge >> "$LOG" 2>&1
  sleep 30
done
echo "=== INCOMPLET $(date) ===" >> "$LOG"
exit 1
