#!/usr/bin/env bash
# Leak scan over the working tree AND git history. Exit 1 on any finding.
# Rules: no e-mail-shaped string except the reserved synthetic domain (example.test), no Drive/notebook paths,
# no source-company/person terms. Extra private terms can be supplied via LEAK_EXTRA_TERMS (regex, never committed).
cd "$(dirname "$0")/.." || exit 2
TERMS='profiling|barbara|axiom|mydrive|/content/drive|drive\.google|colab\.research|c[oó]pia_de|dadosfunil|paretodeuso|/home/[a-z]+/'
EMAIL='[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9-]+\.[A-Za-z.]+'
OKMAIL='@example\.test$'
tmp=$(mktemp)
files=$(git ls-files -co --exclude-standard | grep -v '^scripts/leak_scan.sh$')

for f in $files; do
  [ -f "$f" ] || continue
  grep -I -n -i -E "$TERMS" "$f" 2>/dev/null | sed "s#^#TERM $f:#" >> "$tmp"
  grep -I -n -o -i -E "$EMAIL" "$f" 2>/dev/null | grep -v -i -E "$OKMAIL" | sed "s#^#EMAIL $f:#" >> "$tmp"
  grep -I -n -w "Blocks" "$f" 2>/dev/null | sed "s#^#TERM $f:#" >> "$tmp"
  [ -n "$LEAK_EXTRA_TERMS" ] && grep -I -n -i -E "$LEAK_EXTRA_TERMS" "$f" 2>/dev/null | sed "s#^#EXTRA $f:#" >> "$tmp"
done

if git rev-parse HEAD >/dev/null 2>&1; then
  hist=$(git log -p --all --no-color -- . ':(exclude)scripts/leak_scan.sh' 2>/dev/null | grep -E '^\+')
  echo "$hist" | grep -I -i -E "$TERMS" | sed 's/^/HISTORY TERM: /' >> "$tmp"
  echo "$hist" | grep -o -i -E "$EMAIL" | grep -v -i -E "$OKMAIL" | sed 's/^/HISTORY EMAIL: /' >> "$tmp"
  echo "$hist" | grep -I -w "Blocks" | sed 's/^/HISTORY TERM: /' >> "$tmp"
  [ -n "$LEAK_EXTRA_TERMS" ] && echo "$hist" | grep -I -i -E "$LEAK_EXTRA_TERMS" | sed 's/^/HISTORY EXTRA: /' >> "$tmp"
fi

if [ -s "$tmp" ]; then echo "LEAK SCAN: findings"; head -40 "$tmp"; rm -f "$tmp"; exit 1; fi
echo "LEAK SCAN: clean (working tree + history)"; rm -f "$tmp"
