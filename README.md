# Shellac: A distributed web accelerator

Shellac is an HTTP/1.1 caching proxy for Linux. It is designed to handle thousands of client connections at once, and aggresively cache content in a disributed pool of memory. Shellac can be used in a number of different configurations. In the simplest setup Shellac can provide conceptually similar functionality to <a href="https://www.varnish-cache.org">Varnish</a> and <a href="http://www.squid-cache.org">Squid</a>: a single-host cache for one or more web servers. But owing to an event-driven architecture not unlike <a href="http://nginx.com">Nginx</a> and <a href="http://haproxy.1wt.eu">HAproxy</a>, you can safely put Shellac in front of many more origin servers than you could Varnish or Squid. Also, Shellac allows you to grow your cache capacity well beyond a single host: in fact, it will let you "glue" together extra memory on as many machines as you can afford. 

Slides can be found <a href="http://goo.gl/OGjlVW">here</a>.

## Background

Web accelerators have become quite popular for scaling web services, especially where expensive page rendering is involved. They can provide a performance boost by serving requests directly from memory, and help squeeze more out of web servers and applications by sheltering them from uncessary work. Traditionally, acclerators have been designed to use extra memory on a single machine to cache for a single web server. A service that load balances traffic across 8 web servers likely has 8 separate caches, one in front of each server. By contrast, Shellac attempts to be fast enough to cache for many upstream servers and instead of maintaining separate caches, creates a single logical cache out of extra memory across the cluster.  

## Architecture

At its core Shellac is a high-performance, event-driven HTTP/1.1 proxy server designed specifically for modern Linux kernels. It manages thousands of concurrent client connections with <i>epoll</i> and avoids copies into user space with <i>splice</i>. The distributed cache is built on <a href="http://memcached.org">Memcached</a>. The current prototype is written in Python using fast C bindings to <a href="https://github.com/joyent/http-parser">http-parser</a>, libc's <i>splice</i>, and libmemcached. 

## Performance

Actual benchmarks will be forthcoming. In the meantime, below is a <b>very rough sketch</b> of one of the graphs that I would <i>like</i> to be able to draw (eventually with the axes labelled!). Another version of this graph might show the memory usage to be the same but a much higher RPS for Shellac, if the working set were large enough. 

<img src="https://dl.dropboxusercontent.com/u/55111805/Shellac.png" />

<b>Overview</b>
Shellac has a fundamentally more scalable architecture than Varnish. It is event-driven and aggressively avoids copying data into user space. Also, just intuitively, the hit rate for a distributed cache will be higher than <i>n</i> local caches (if any server in the cluster has already generated the cacheable object it will be a hit, as opposed to only if the handling server has generated it). Upstream applications are sufficiently slow as to make retrieving objects from memory on neighboring machines faster than regenerating the content locally. Furthermore, a distributed cache reduces overall memory usage (across the cluster) by a factor of the number of web servers in your cluster: if your working set is 1 GB, then it is spread across all machines instead of duplicated on each one.

<b>Optimization</b>
Shellac uses consistent hashing to avoid rebuilding the entire cache in the event of node failure, however, no effort is made to improve locality. The current prototype does not support session tagging/routing, but if it did one could imagine caching accessed objects locally to improve locality for future requests in the same session. This is future work.  

## Configurations

There are two distinct ways to use Shellac, and a third hybrid option. There are range of possible configurations and trade-offs. 

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

Copyright &copy; Kalan MacRow, 2013 &mdash; Licensed under The MIT License (MIT)




