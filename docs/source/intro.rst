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
