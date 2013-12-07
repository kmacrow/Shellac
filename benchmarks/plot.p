# output as png image
set terminal png

# save file
set output "benchmark.png"

# graph title
set title "ab -n 100 -c 1"

# nicer aspect ratio for image size
set size 1,0.7

# y-axis grid
set grid y

# x-axis label
set xlabel "Request"

# y-axis label
set ylabel "Response time (ms)"

# plot ab data using column 9 with smooth sbezier lines
plot "baseline.dat" using 9 smooth sbezier with lines title "Apache 2.2",\
	 "varnish.dat" using 9 smooth sbezier with lines title "Varnish 3.0",\
	 "shellac.dat" using 9 smooth sbezier with lines title "Shellac 0.1.0a"