# Shellac: A distributed caching proxy

Shellac is an HTTP/1.1 distributed caching proxy for Linux. It is incredibly fast and capable of handling 10K+ client connections at once, and potentially many more. Shellac can be used in a number of different configurations. In the simplest setup Shellac can provide conceptually similar functionality to <a href="#">Varnish</a> and <a href="#">Squid</a>: a single-host cache for 1 - <i>n</i> web servers. But owing to an event-driven architecture not unlike <a href="#">nginx</a> and <a href="#">HAproxy</a>, you can safely put Shellac in front of many more origin servers than you could Varnish or Squid. And Shellac allows you to grow your cache capacity well beyond a single-host: in fact, it will let you "glue" together the extra memory on as many machines as you can afford.    

Slides can be found <a href="http://goo.gl/OGjlVW">here</a>.

## Background

Web server accelerators and caches have proven very useful for scaling services. They can provide a performance boost by serving requests directly from memory, and help squeeze a little bit more out of web servers and applications by sheltering them from uncessary work. Traditionally, acclerators have been designed to use the memory available on a single machine to cache for a handful (and often just one) web server. A service that load balances across 8 web servers likely has 8 separate caches, one in front of each server. However, it is commonplace for <i>applications</i> to use <i>distributed</i> caches (e.g. <a href="#">memcached</a>) to save costly database queries or expensive page renderings. Shellac attempts to bring the advantages of a scalable, distributed cache to the HTTP layer. As the memory available in the cluster increases, so does your hit rate.

## Architecture

Shellac is a <a href="#">C10K</a> server. Instead of allocating an expensive OS thread for each connection, it uses <code>epoll</code> to manage thousands of sockets in a single process and <code>splice</code> to avoid copying data into user space. Shellac's distributed cache is built on <a href="#">Memcached</a>. The current prototype is written in Python, using the ctypes interface to wrap <code>libc</code>'s <code>epoll</code> and <code>splice</code>.

## Configurations

There are two distinct ways to use Shellac, and a third hybrid option. Within each high-level configuration there is a range of possible deployments, each with trade-offs. 

<b>Web accelerator</b>
You can replace each instance of Varnish with Shellac and gain the advantage of a larger cache shared accross your web servers. 

<b>Load balancer</b>
You can use Shellac as a load balancer for your backend web servers to scale performance and increase availability.

<b>Caching load balancer</b>
You can put an instance of Shellac in front of all of your backend servers and use their (and or dedicated cache machines' memory) as a single large cache for Shellac. In this configuration you can save a hop from the load balancer to the cache.

## Performance

This section has yet to be written. I intend to do at least a cursory evaluation of Shellac's performance for the aforementioned configurations. I think the most interesting result will be how it compares to a traditional Varnish deployment.

## Getting started

Shellac is built and tested on Ubuntu 12.04 (Precise). You should grab the latest release <a href="https://github.com/kmacrow/Shellac/releases">here</a>, and do the usual thing:

```bash
$ tar -xvzf shellac-x.x.x.tar.gz
$ cd shellac-x.x.x
$ ./configure
$ make
$ sudo make install
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




