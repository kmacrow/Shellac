#!/usr/bin/env bash

# n = 45 * c where c is number of clients. 

ab -k -n 200 -c 2 -g baseline.dat -H "Accept-Encoding: gzip" http://127.0.0.1/
ab -k -n 200 -c 2 -g shellac.dat -H "Accept-Encoding: gzip" http://127.0.0.1:8080/
#ab -n 100 -c 1 -g varnish.dat http://127.0.0.1:9090/

gnuplot plot.p
