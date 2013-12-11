# Shellac: a distributed web accelerator

Shellac is an HTTP/1.1 caching proxy for Linux. It is designed to handle thousands of client connections at once, and aggressively cache content in a distributed key/value store. Shellac can be used in a number of different configurations. In the simplest setup it can provide conceptually similar functionality to <a href="https://www.varnish-cache.org">Varnish</a> and <a href="http://www.squid-cache.org">Squid</a>, but Shellac allows you to grow your cache capacity well beyond a single host. In fact, it will let you "glue" together extra memory on as many machines as you can afford to cache expensive responses. 

<!-- todo link to slidedeck instead -->
Slides (including graphs) can be found <a href="https://speakerdeck.com/kmacrow/shellac-a-distributed-web-accelerator">here</a>.

## Background

Web accelerators have become extremely popular for scaling web services, especially where expensive page rendering is involved. <a href="http://royal.pingdom.com/2012/07/11/how-popular-is-varnish/">Many of the top</a> news, e-commerce and blogging platforms make extensive use of HTTP caches in their networks. They can provide a performance boost by serving requests directly from memory, and help squeeze more out of web and application servers by sheltering them from uncessary work. 

Traditionally, accelerators have been designed to use extra memory on a single machine to cache for a single web server. For example, a service that load balances traffic across 8 web servers likely has 8 separate caches, one in front of each server. By contrast, Shellac is fast enough to cache for many upstream servers and instead of maintaining separate caches, creates a single logical cache out of extra memory across the entire cluster.  

## Related Projects

There are a number of related projects, Wikipedia has a nice table enumerating features for many of them <a href="http://en.wikipedia.org/wiki/Web_accelerator#Comparison_2">here</a>.

<a href="http://varnish-cache.org">Varnish Cache</a> and <a href="http://www.squid-cache.org">Squid Cache</a> are the most relevant. Varnish is a thread-per-request HTTP/1.1 proxy server capable building a local cache in RAM or on disk. Squid is also a thread-per-request caching server, but has a protocol-independent core. Squid can cache for a number of layer 7 protocols, including HTTP, FTP, SMTP, etc. In the load balancing category, Shellac's server architecture is inspired by <a href="http://haproxy.1wt.eu">HAproxy</a> and <a href="http://nginx.com">Nginx</a>.

## Architecture

At its core Shellac is a high-performance HTTP/1.1 proxy server designed specifically for modern Linux kernels. It manages thousands of concurrent client connections using level-triggered edge-polling (epoll) and multiplexes requests onto persistent connections upstream. The distributed cache is built on <a href="http://memcached.org">Memcached</a>. The current prototype is written in Python with a ctypes wrapper around libmemcached.

## Performance

This section contains an overview of Shellac's performance characteristics, including some discussion of <a href="http://httpd.apache.org/docs/2.2/programs/ab.html">Apache Benchmark</a> (ab) results for Shellac 0.1.0a "Hutch". 

<b>Overview</b>

Shellac has a fundamentally more scalable architecture than existing accelerators. The proxy server itself is single-threaded and event-driven, while the cache is built on the battle-proven Memcached. The expected hit rate for a distributed cache in this context is slightly higher than for <i>n</i> local caches (if any server in the cluster has already generated the cacheable object it will be a hit, as opposed to only if the responding server has generated it). Upstream web applications are generally sufficiently slow as to make retrieving objects from memory on machines in the same datacenter faster than regenerating the content locally. Furthermore, a distributed cache reduces overall memory usage (across the cluster) by a factor of the number of web servers in your cluster compared to isolated caches: if your working set is 1 GB, then it is spread across all machines instead of duplicated on each one. A distributed cache also allows you to better separate concerns: cache memory does not have to be on the same machine as Shellac or your web/application servers. Also, consistent hashing ensures that if a cache node fails the entire cache is not lost. 

<b>Python</b>

Shellac 0.1.0a "Hutch" is a proof of concept written in vanilla Python and tested under CPython. It does not use any frameworks and has no significant dependencies outside of the standard library. Being a single-threaded "reactor", Shellac largely avoids all of the problems associated with the Python Global Interpreter Lock (GIL), which is known to <a href="http://www.dabeaz.com/python/GIL.pdf">plague</a> multi-threaded programs. Shellac is not compute bound, but every effort is made to push iteration down into native code via language constructs (i.e. list generators) or native functions (map, filter, join, etc.) Unfortunately, all function calls (and especially method calls) present relatively significant overhead and not all iteration can be offloaded to native code. In particular, Shellac's main event loop suffers as a result of these and other overheads. There is a fun overview of things to do (and to avoid) in writing performant Python <a href="https://wiki.python.org/moin/PythonSpeed/PerformanceTips">here</a>.  

<b>Profiling</b>

Shellac's reasonably good performance in benchmarks is largely thanks to extensive profiling and tweaking with <a href="http://docs.python.org/2/library/profile.html#module-cProfile">cProfile</a>, which was able to weed out a number of surprising bottlenecks. Hand optimizing string concatenations, regular expression compilation, <code>dict</code> accesses via <code>get()</code> and a number of other things proved to be significant performance wins. Profiling also lead to a more efficient use of epoll that saved tens of thousands of function calls by continuously updating which events the server is interested in for each socket.   

<b>Benchmarks</b>

Tools used: <a href="http://httpd.apache.org/docs/2.2/programs/ab.html">ab</a>, <a href="http://www.joedog.org/siege-home/">siege</a>, <a href="http://www.hpl.hp.com/research/linux/httperf/">httperf</a>, <a href="http://dag.wiee.rs/home-made/dstat/">dstat</a>, <a href="http://www.gnuplot.info">gnuplot</a>.

In all of the benchmarks that follow, HTTP/1.1 Keep-Alive (request pipelining) and Gzip compression were enabled. The <code>ab</code> tool generates load by simulating a number of concurrent clients hitting the same URI for some total number of requests. The Apache Benchmark (ab) command looks something like this:

```bash
ab -k -n 10000 -c 1000 -g out.dat -H "Accept-Encoding: gzip" http://127.0.0.1/page.php
```
A bare bones Apache 2.2 instance was used as a baseline for performance. The Shellac "Hutch" prototype is then compared to the commercially-supported, open-source Varnish Cache (<a href="http://varnish-cache.org">varnish-cache.org</a>). Varnish is easily the most popular HTTP/1.1 cache around, known for it's reliability, performance and flexibility via <a href="https://www.varnish-cache.org/trac/wiki/VCL">VCL</a>. Three metrics were evaluated: requests served per second (RPS), peak memory usage per node, and transfer rate. The benchmarks were run on a cluster of 4 <tt>m1.large</tt> AWS instances (quad-core Xeon, 8GB RAM, moderate network performance) with an Elastic load balancer in front. 

<b>Aside:</b> Because my last statistics professor, frothing at the mouth, chased me out of the Math Annex with a blackboard pointer<sup>1</sup>, I elected to be conservative and in all cases plot Shellac's worst of three runs against Apache and Varnish's best of three.  

<img src="https://dl.dropboxusercontent.com/u/55111805/ab.png" />
<div align="center">
<i>Apache, Varnish and Shellac serving 10K requests (total) from 1K concurrent clients.</i>
</div>

The above graph shows all three servers under load. Not surprisingly (but maybe surprisingly!) Apache is the slowest, while Varnish and Shellac are neck-and-neck. Zooming in we can see that Shellac is marginally faster (until the end), even in its worst of three runs.

<img src="https://dl.dropboxusercontent.com/u/55111805/ab-2.png" />
<div align="center">
<i>Varnish and Shellac serving 10K requests (total) from 1K concurrent clients.</i>
</div> 

Zooming in even further on the left side of the graph reveals just how close Varnish and Shellac are. <b>Perhaps the most interesting thing here is that the Shellac prototype is not crashing under this load</b>. 

<img src="https://dl.dropboxusercontent.com/u/55111805/ab-3.png" />

Looking at the mean RPS (below) it is clear that Shellac is quite competitive with Varnish across three different benchmarks. <i>Static</i> involves serving a small static page, <i>Dynamic 1</i> involves serving a trivial dynamic page and <i>Dynamic 3</i> simulates serving a non-trivial dynamic page comparable to rendering a blog article. In Shellac's <i>Dynamic 2</i> run shown here problems with Memcached caused Shellac to hit Apache more than it should have, which manifests itself as higher memory usage in next graph. 

<img src="https://dl.dropboxusercontent.com/u/55111805/rps.png" /> 

Finally, a somewhat superficial look at memory usage across the cluster demonstrates that even as a Python prototype, Shellac's memory overheads are very comparable to those of Varnish. This graph shows mean <b>peak</b> memory usage for a node in the cluster. Again, Shellac's worst against the others' best. In <i>Dynamic 2</i> for Shellac we can see the cost of hitting Apache when Memcached sputtered. Despite comparable peak usage, I state without proof that Shellac's memory overhead was actually significantly lower than Varnish.

<img src="https://dl.dropboxusercontent.com/u/55111805/mem.png" />  

## Conclusion

Shellac is nowhere near ready for business, however, the early results are quite promising. In the worst case Shellac keeps pace with Varnish, a mature commercially-maintained server running optimized native code. Furthermore, the benchmarks I have been able to complete to date are not extremely representative of the type of load that Shellac is designed for. Future work will involve stabilizing the server, extending and automating the perf. test bench, ensuring HTTP/1.1 compliance, and eventually a port to C. In the slightly longer term, replacing Memcached with a purpose-built cache will likely make sense. Finding a way to expose low-level counters, queue depths, cache statistics, etc. for real-time analysis, logging, and monitoring are also priorities. A sketch of the roadmap can be found <a href="https://github.com/kmacrow/Shellac/issues/milestones">here</a>.

1. Okay, that didn't really happen. But statistics has not historically been my strong suit.

## Getting started

Shellac 0.1.0a "Hutch" can be downloaded <a href="https://github.com/kmacrow/Shellac/releases">here</a>. The code contained in that release snapshot was used to run the benchmarks discussed here.

Shellac is built and tested on Ubuntu 12.04 (Precise). You should grab the latest release <a href="https://github.com/kmacrow/Shellac/releases">here</a>, and do this:

```bash
$ tar -xvzf Shellac-x.x.x.tar.gz
$ cd Shellac-x.x.x
$ ./devenv
$ python setup.py install
```
And then to run the server,

```bash
$ python -m SimpleHTTPServer 8080
$ shellac -s localhost:8080 -c localhost -p 9090
```
See <code>shellac -h</code> for more options and details.

## Contributors

<dl>
	<dt>Kalan MacRow</dt>
	<dd><a href="#">@k16w</a></dd>
</dl>

Feel free to contact me or submit a pull request if you are interested in contributing. 

Copyright &copy; Kalan MacRow, 2013-14 &mdash; Licensed under The MIT License (MIT)




