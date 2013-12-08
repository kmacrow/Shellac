#!/usr/bin/env bash

ab -k -n 400 -c 10 -g varnish.dat -H "Accept-Encoding: gzip" http://127.0.0.1:6081/
