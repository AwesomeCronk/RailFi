#! /bin/bash
echo "Setting up loco on $1"
echo "boot.py -> boot.py"
upyfile "$1" push boot.py boot.py
echo "main.py -> main.py"
upyfile "$1" push main.py main.py
# echo "baseConfig.txt > config.txt"
# upyfile $1 push config.txt baseConfig.txt
echo "Done"
