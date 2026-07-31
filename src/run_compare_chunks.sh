#!/bin/zsh
# Extension (a) : comparaison chunks 512 vs 1024, sequentielle et auto-reparante.
ROOT=${0:A:h:h}
cd "$ROOT"
LOG=eval/cache/compare-chunks.log
echo "=== demarrage $(date) ===" >> $LOG
.venv/bin/python src/filter_backmatter.py 1024 >> $LOG 2>&1
for TABLE in bunge_1024 bunge_512; do
  for i in 1 2 3; do
    [ -f "eval/cache/hits-$TABLE.json" ] && break
    echo "--- eval $TABLE passe $i $(date) ---" >> $LOG
    BUNGE_TABLE=$TABLE .venv/bin/python src/eval_retrieval.py >> $LOG 2>&1
  done
done
echo "=== COMPAREDONE $(date) ===" >> $LOG
