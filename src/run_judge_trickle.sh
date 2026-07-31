#!/bin/zsh
# Complète un run fingerprinté au rythme du quota Cerebras.
ROOT=${0:A:h:h}
cd "$ROOT"
PROFILE=${EVAL_PROFILE:-public_v1}
LOG="eval/cache/run-judge-${PROFILE}.log"

for i in $(seq 1 48); do
  STATUS=$(EVAL_PROFILE="$PROFILE" .venv/bin/python src/eval_ragas.py --status)
  ANSWERS=$(print -r -- "$STATUS" | .venv/bin/python -c \
    'import json,sys; d=json.load(sys.stdin); print(f"{d[\"answers\"]}/{d[\"answers_expected\"]}")')
  NOTES=$(print -r -- "$STATUS" | .venv/bin/python -c \
    'import json,sys; d=json.load(sys.stdin); print(f"{d[\"notes\"]}/{d[\"notes_expected\"]}")')
  echo "--- passe $i : $ANSWERS réponses, $NOTES notes $(date) ---" >> "$LOG"
  if [ "${ANSWERS%/*}" != "${ANSWERS#*/}" ]; then
    echo "=== ERREUR réponses incomplètes : $ANSWERS ===" >> "$LOG"
    exit 2
  fi
  if [ "${NOTES%/*}" = "${NOTES#*/}" ]; then
    echo "=== FULLDONE $(date) ===" >> "$LOG"
    exit 0
  fi
  EVAL_PROFILE="$PROFILE" .venv/bin/python src/eval_ragas.py --judge >> "$LOG" 2>&1
  sleep 1800
done
echo "=== INCOMPLET $(date) ===" >> "$LOG"
exit 1
