#!/bin/sh

echo "Starting ingressroute listener"

sleep 3

python /main.py | tee /out.log
