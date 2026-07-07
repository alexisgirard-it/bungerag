#!/bin/zsh
cd ~/BungeRAG
LOG=eval/cache/run-panoramic.log
echo "=== demarrage $(date) ===" >> $LOG
for i in 1 2 3 4; do
  .venv/bin/python src/eval_panoramic.py >> $LOG 2>&1 && break
  sleep 60
done
grep -q "lecture côte à côte" $LOG && echo "=== PANODONE $(date) ===" >> $LOG
