#!/bin/bash
cd "$(dirname "$0")"
echo "Avvio la Hub in locale su http://localhost:8745 ..."
echo "Lascia aperta questa finestra finché stai navigando: chiudendola, il sito si ferma."
(sleep 1 && open "http://localhost:8745/") &
/usr/bin/python3 -m http.server 8745 --bind 127.0.0.1
