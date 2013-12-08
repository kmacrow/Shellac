
set terminal png
set output "requests.png"
set title "Apache Benchmark"
set size 1,0.7
set grid y
set xlabel "Request"
set ylabel "Response time (ms)"

plot "baseline.dat" using 9 smooth sbezier with lines title "Apache 2.2",\
	 "varnish.dat" using 9 smooth sbezier with lines title "Varnish 3.0",\
	 "shellac.dat" using 9 smooth sbezier with lines title "Shellac 0.1.0a"