OpenNode Management Service
===========================

OpenNode Management Service (OMS) is a modular framework for creating management applications. Its initial target was
hosting the OMS [Knot cloud management platform](https://github.com/opennode/opennode-knot).

OMS main documentation is generated and can be [viewed online](http://opennodecloud.com/docs/opennode.oms.core/index.html).

Requirements
------------

Currently the only requirements are Python 2.7, its headers, GCC and GNU Make.

### Mac OS X

1. Install Python 2.7 in one of the ways:

    * using MacPorts

            sudo port install python27
        
    * using Homebrew

            brew install python

    * manually

### Ubuntu

On Ubuntu Python 2.7 is shipped out of the box, so no installation is needed.

To work-around version incompatibility between system-wide setuptools and the one needed for buildout, virtualenv is needed. This work-around, though, results in a warning `BROKEN_DASH_S_WARNING` each time a script in `bin/` is run. It can be safely ignored.

1. Install build tools:

        sudo apt-get install --yes g++ make

2. Install Python headers:

        sudo apt-get install --yes python-dev

3. Install Virtualenv:

        sudo apt-get install --yes python-virtualenv

Building
========

1. Get the code:

        git clone git@github.com:opennode/opennode-management.git
        cd opennode-management

2. Boostrap buildout:

    * Without Virtualenv:

            python bootstrap.py -v 1.7.0

    * With Virtualenv:

            virtualenv --setuptools venv
            venv/bin/pip install setuptools==1.3
            venv/bin/python bootstrap.py -v 1.7.0

3. Run buildout:

        bin/buildout

4. Restrict access to Python egg cache to avoid future warnings:

        chmod go-rwx -R $HOME/.python-eggs

__Note:__ Steps 2 and 3 may fail with timeout error. It happens due to heavy load on PyPi package repository. It is safe to repeat the failed command once again.

__Note:__ Steps 1, 2 and 4 must be done only once. The 3rd one must be done each time `buildout.cfg` gets changed.

Running
=======

1. Setup user accounts with the `bin/omspasswd` utility:

        bin/omspasswd -g admins -a john
        bin/omspasswd -g users -a jane

2. Start OpenNode Management Service:

        bin/omsd

3. It should be possible to log into OMS shell using credentials specified in 1st step:

        ssh -l john localhost -p 6022
    
Testing
=======

1. `./test.sh`

Plugins
=======

You can quickly enable plugins by adding the plugin buildout snippet to the `eggnest` dir, e.g:

   `bin/plugin install opennode.oms.onc`

This will download the published egg for the plugin.
If you want to use a development plugin you have to specify the plugin checkout:

   `bin/plugin install opennode.oms.knot -d ../opennode-knot`

Development
===========

During development, you can use the autoreload mode with `bin/omsd -d`.
If you make changes in the dependencies, just rerun `bin/buildout`.
You can use `bin/buildout -o` to avoid waiting for the network, if you already have the eggs in the cache.

You can get a python prompt with the correct python path with `bin/python`.

High level architecture
=======================

The core consists of:

* The models:

    These are mostly ORM backed and some transient classes which
    contain CRUD and most of the domain logic.

* Traversal:

    Mapping of URIs/paths to model objects,
    i.e. /datacentres/123/computes/9 -> <Compute object>.

* Interaction layers a.k.a endpoints (in Twisted terminology):

    This is a thin layer that takes an incoming request/interaction
    (either SSH/vconsole, HTTP or WebSocket) which is always bound to
    a URI/path (cwd in SSH, request URI in HTTP/Websocket) and maps
    it, using traversal, to a domain object and executes appropriate
    methods and returns a result.

    This layer can be thought of as the controller.

    The interaction layer is as thin as possible as traversal, domain
    logic and security are in the core, and serialisation is generic.


Interaction layers/endpoints
============================

The primary interaction layer is the HTTP REST endpoint which contains
an HTTP request handler and a set of views, one for each content
type. The views can either be generic over content types, or
specialised for specific models. Generic is preferred over specialised
though.

The WebSocket endpoint is in big part complementary to the HTTP REST
endpoint. It is mostly an alternative carrier or transport mechanism
for individual HTTP-like requests. In addition, it is used to push a
stream of data/events to the browser for real time updates of the UI.
As HTTP REST like requests can be transported from client to server
over this layer, it also provides a performance boost over classic
HTTP as it eliminates any request overhead both in terms of
responsiveness and network/resource usage. It is also easier to manage
than classic HTTP as browser security restrictions do not apply to
WebSocket connections.

The SSH virtual console endpoint provides a bash-like pseudo shell
over SSH that exposes a filesystem-like hierarchy to navigate in and
manage the server infrastructure environment. It provides or will
provide all the basic shell-like commands such as `cd`, `ls`, `pwd`,
`cat`, `mv`, `cp` and `rm`. It also provides the generic command `set`
to modify attributes of objects.

License
-------

OpenNode Management Service is released under an open-source
[Apache v2](http://www.apache.org/licenses/LICENSE-2.0) license. Commercial support
is possible, please contact <info@opennodecloud.com> for more information.
