# Shellac: a distributed web "accelerator"

Shellac is an HTTP/1.1 caching proxy for Linux. It is designed to handle thousands of client connections at once, and aggressively cache content in a distributed pool of memory. Shellac can be used in a number of different configurations. In the simplest setup it can provide conceptually similar functionality to <a href="https://www.varnish-cache.org">Varnish</a> and <a href="http://www.squid-cache.org">Squid</a>: a single-host cache for one or more web servers. But owing to an event-driven architecture not unlike <a href="http://nginx.com">Nginx</a> and <a href="http://haproxy.1wt.eu">HAproxy</a>, you can safely put Shellac in front of many more origin servers than you could Varnish or Squid. Also, Shellac allows you to grow your cache capacity well beyond a single host: in fact, it will let you "glue" together extra memory on as many machines as you can afford. 

Slides can be found <a href="http://goo.gl/OGjlVW">here</a>.

## Background

Web accelerators have become quite popular for scaling web services, especially where expensive page rendering is involved. They can provide a performance boost by serving requests directly from memory, and help squeeze more out of web servers and applications by sheltering them from uncessary work. Traditionally, acclerators have been designed to use extra memory on a single machine to cache for a single web server. A service that load balances traffic across 8 web servers likely has 8 separate caches, one in front of each server. By contrast, Shellac attempts to be fast enough to cache for many upstream servers and instead of maintaining separate caches, creates a single logical cache out of extra memory across the cluster.  

## Architecture

At its core Shellac is a high-performance, event-driven HTTP/1.1 proxy server designed specifically for modern Linux kernels. It manages thousands of concurrent client connections with <i>epoll</i> and avoids copies into user space with <i>splice</i>. The distributed cache is built on <a href="http://memcached.org">Memcached</a>. The current prototype is written in Python using fast C bindings to <a href="https://github.com/joyent/http-parser">http-parser</a>, libc's <i>splice</i>, and libmemcached. 

## Performance

Actual benchmarks will be forthcoming. In the meantime, below is a <b>very rough sketch</b> of one of the graphs that I would <i>like</i> to be able to draw. It corresponds to a standard <a href="http://httpd.apache.org/docs/2.2/programs/ab.html">ab</a> benchmark of a cluster of <i>n</i> backend servers. The <code>ab</code> tool generates load by hitting a single URI repeatedly with 1 - <i>c</i> concurrent connections. I account for &beta; by arguing that Shellac is higher performance by design (event-driven, request pipelining, etc.) and has a higher expected cache hit rate. I argue &delta; by observing that in a distributed cache only a single copy of the object will be stored in RAM, as opposed to <i>n</i> copies (which also have to be generated <i>n</i> times!). It is also worth noting that a cache hit for Shellac should be served from local memory approximately 1/<i>n</i> of the time, so not all cache locality is lost.

<img src="https://dl.dropboxusercontent.com/u/55111805/Shellac.png" />

<b>Overview</b>

Shellac has a fundamentally more scalable architecture than existing accelerators. It is event-driven and aggressively avoids copying data into user space. Also, just intuitively, the hit rate for a distributed cache will be higher than <i>n</i> local caches (if any server in the cluster has already generated the cacheable object it will be a hit, as opposed to only if the handling server has generated it). Upstream applications are sufficiently slow as to make retrieving objects from memory on neighboring machines faster than regenerating the content locally. Furthermore, a distributed cache reduces overall memory usage (across the cluster) by a factor of the number of web servers in your cluster: if your working set is 1 GB, then it is spread across all machines instead of duplicated on each one.

<b>Optimizations</b>

Shellac uses consistent hashing to avoid rebuilding the entire cache in the event of node failure, however, no effort is made to improve locality. The current prototype does not support session tagging/routing, but if it did one could imagine caching accessed objects locally to improve locality for future requests in the same session. This is future work. Also, there is an opportunity to transform or analyze objects before they are cached. Shellac currently doesn't take advantage of the opportunity to do anything smart.  

<b>Benchmarks</b>

Tools: <a href="http://httpd.apache.org/docs/2.2/programs/ab.html">ab</a>, <a href="http://www.joedog.org/siege-home/">siege</a>, <a href="http://www.hpl.hp.com/research/linux/httperf/">httperf</a>.

<!--
First of all, I'd like to benchmark RPS for Nginx on its own, and then put Shellac in front of it (without caching) to get a lower-bound on Shellac's overhead. With that I would like to look at Shellac vs. Varnish with a single web server, and then multiple servers using HAproxy to load balance. Finally, it would be interesting to compare Shellac and HAproxy itself. I would not expect the Shellac prototype to fare well against the battle-hardened HAproxy, but it might give some indication of the Python overhead.
-->

## Configurations

There are two distinct ways to use Shellac, and a third hybrid option. 

<b>Accelerator</b>

You can replace each instance of Varnish with Shellac to increase vertical scalability and free up RAM for your web servers and applications.

<b>Load balancer</b>

You can use Shellac as a load balancer for your backend web servers to scale out and increase availability.

<b>Accelerator + load balancer</b>

You can put an instance of Shellac in front of all of your backend servers and use their (or other machines' memory) as a single cache.

## Getting started

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
$ shellac --port 9090 --origin localhost:8080 
```
See <code>shellac -h</code> for more options and details.

## Contributors

<dl>
	<dt>Kalan MacRow</dt>
	<dd><a href="#">@k16w</a></dd>
</dl>

Copyright &copy; Kalan MacRow, 2013-14 &mdash; Licensed under The MIT License (MIT)




