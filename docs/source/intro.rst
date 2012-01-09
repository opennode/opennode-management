Introduction
============

OMS core is a modular container built primarily for hosting the OMS Knot cloud management platform

Quick Start
===========

Installing
----------

Quick installation of OMS core on Linux:

.. code-block:: sh

  $ curl http://opennodecloud.com/download/oms-core-installer.sh | sh

This will create an 'oms' subdirectory in the current directory.
If you move/rename that directory, please make sure you run the `update.sh` script.

Starting up
-----------

Then you can start oms daemon with:

.. code-block:: sh

  $ cd oms
  $ bin/omsd

Connect
-------

You can connect to the OMS console via ssh:

.. code-block:: sh

  $ ssh root@localhost -l 6022


Plugins
-------

You can install plugins with:

.. code-block:: sh

  $ bin/plugin install knot

Uninstall with:

.. code-block:: sh

  $ bin/plugin uninstall knot

See the currently installed plugins:

.. code-block:: sh

  $ bin/plugin list

And search for other published plugins:

.. code-block:: sh

  $ bin/plugin search [some-regexp]

Dependencies
~~~~~~~~~~~~

Installing a plugin which depends on another plugin(s) will automatically install it's dependencies:

.. code-block:: sh

  $ bin/plugin list
  $ bin/plugin install opennode.oms.onc
  ...
  $ bin/plugin list
  opennode.oms.knot (0.0-5-gd425) [autodep]
  opennode.oms.onc (0.0-320-gc5ca)

Development
~~~~~~~~~~~

You can also install a plugin under development with:

.. code-block:: sh

  $ bin/plugin install knot -d ../opennode-knot


Installing a development plugin which depends on another plugin will fetch the dependency as egg:

  $ bin/plugin list
  $ bin/plugin install opennode.oms.onc -d ../opennode-console-exp
  ...
  $ bin/plugin list
  opennode.oms.knot (0.0-5-gd425) [autodep]
  opennode.oms.onc (0.0-320-gc5ca) [dev]
