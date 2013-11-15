# Shellac: A distributed web accelerator

Shellac is an HTTP/1.1 distributed caching proxy for Linux. It is designed to handle thousands of client connections at once, and aggresively cache content in a disributed pool of memory. Shellac can be used in a number of different configurations. In the simplest setup Shellac can provide conceptually similar functionality to <a href="https://www.varnish-cache.org">Varnish</a> and <a href="http://www.squid-cache.org">Squid</a>: a single-host cache for one or more web servers. But owing to an event-driven architecture not unlike <a href="http://nginx.com">nginx</a> and <a href="http://haproxy.1wt.eu">HAproxy</a>, you can safely put Shellac in front of many more origin servers than you could Varnish or Squid. Shellac allows you to grow your cache capacity well beyond a single host: in fact, it will let you "glue" together extra memory on as many machines as you can afford. You can even dedicate machines to providing cache memory.    

Slides can be found <a href="http://goo.gl/OGjlVW">here</a>.

## Background

Web server accelerators and caches have proven very useful for scaling web services. They can provide a performance boost by serving requests directly from memory, and help squeeze more out of web servers and applications by sheltering them from uncessary work. Traditionally, acclerators have been designed to use the memory available on a single machine to cache for a single web server. A service that load balances traffic across 8 web servers likely has 8 separate caches, one in front of each server. <b>Shellac aims to bring the advantages of a scalable, distributed cache to the HTTP layer.</b> 

## Architecture

Shellac attempts to solve the <a href="http://www.kegel.com/c10k.html">C10K</a> problem. Instead of allocating an expensive OS thread for each connection, it uses <code>epoll</code> to manage thousands of sockets in a single process and <code>splice</code> to avoid copying data into user space. Shellac's distributed cache is built on <a href="http://memcached.org">Memcached</a>. The current prototype is written in Python using C bindings for fast <a href="https://github.com/benoitc/http-parser/">http parsing</a> and access to libmemcached.

## Configurations

There are two distinct ways to use Shellac, and a third hybrid option. There are range of possible configurations and trade-offs. 

<b>Accelerator</b>
You can replace each instance of Varnish with Shellac and gain the advantage of a larger cache shared accross your web servers. 

<b>Load balancer</b>
You can use Shellac as a load balancer for your backend web servers to scale performance and increase availability.

<b>Accelerator + load balancer</b>
You can put an instance of Shellac in front of all of your backend servers and use their (or other machines' memory) as a single cache. 

## Performance

I'm not sure that this will actually work :-) Evaluation will be forthcoming.

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
$ sudo shellac --origin localhost:8080 
```
See <code>shellac -h</code> for more options and details.

## Contributors

<dl>
	<dt>Kalan MacRow</dt>
	<dd><a href="#">@k16w</a></dd>
</dl>

Copyright &copy; Kalan MacRow, 2013 &mdash; Licensed under The MIT License (MIT)




