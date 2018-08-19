#!/usr/bin/env bash

if grep -Rn "^ *debug(" py/; then
    echo "ERROR: debug commands found"
    exit 1
fi
