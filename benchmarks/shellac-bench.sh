#!/usr/bin/env bash

# n = 45 * c where c is number of clients. 

ab -k -n 400 -c 10 -g baseline.dat -H "Accept-Encoding: gzip" http://127.0.0.1/
ab -k -n 400 -c 10 -g shellac.dat -H "Accept-Encoding: gzip" http://127.0.0.1:8080/
ab -k -n 400 -c 10 -g varnish.dat -H "Accept-Encoding: gzip" http://127.0.0.1:6081/

gnuplot plot.p
