set terminal png
set output "memory.png"
set title "Memory Usage"
set xlabel "Time"
set ylabel "Used (MB)"
set xdata time
set timefmt "%d-%m %H:%M:%S"
set format x "%H:%M"
plot "apache0-mem.dat" using 1:9 smooth sbezier with lines title "Apache 2.2 (1)",\
	 "apache1-mem.dat" using 1:9 smooth sbezier with lines title "Apache 2.2 (2)",\
	 "apache2-mem.dat" using 1:9 smooth sbezier with lines title "Apache 2.2 (3)",\
	 "apache3-mem.dat" using 1:9 smooth sbezier with lines title "Apache 2.2 (4)",\
	 "varnish0-mem.dat" using 1:9 smooth sbezier with lines title "Varnish 3.0 (1)",\
	 "varnish1-mem.dat" using 1:9 smooth sbezier with lines title "Varnish 3.0 (2)",\
	 "varnish2-mem.dat" using 1:9 smooth sbezier with lines title "Varnish 3.0 (3)",\
	 "varnish3-mem.dat" using 1:9 smooth sbezier with lines title "Varnish 3.0 (4)",\
	 "shellac0-mem.dat" using 1:9 smooth sbezier with lines title "Shellac 0.1.0a (1)",\
	 "shellac1-mem.dat" using 1:9 smooth sbezier with lines title "Shellac 0.1.0a (2)",\
	 "shellac2-mem.dat" using 1:9 smooth sbezier with lines title "Shellac 0.1.0a (3)",\
	 "shellac3-mem.dat" using 1:9 smooth sbezier with lines title "Shellac 0.1.0a (4)"
