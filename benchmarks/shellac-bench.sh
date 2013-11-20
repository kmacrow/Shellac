#!/usr/bin/env bash

ab -n 8000 -c 100 -g out.dat http://127.0.0.1:8080/

gnuplot plot.p
