#!/usr/bin/env bash

ab -k -n 400 -c 10 -g shellac.dat -H "Accept-Encoding: gzip" http://127.0.0.1:8080/
