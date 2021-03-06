Introduction
============

OMS core is a modular container built primarily for hosting the OMS Knot cloud management platform

Quick Start
===========

Installing
----------

Quick installation of OMS core on Linux:

.. code-block:: sh

  $ curl -s http://opennodecloud.com/download/oms-core-installer.sh | sh

This will create an 'oms' subdirectory in the current directory.
If you move/rename that directory, please make sure you run the `update.sh` script.

If you prefer you can specify the target directory with:

.. code-block:: sh

  $ curl -s http://opennodecloud.com/download/oms-core-installer.sh > oms-core-installer.sh
  $ sh oms-core-installer.sh --target /opt/oms

The installer will check if you have `python2.7`, otherwise it will tell you
how to proceed by automatically installing a fresh python 2.7 with pythonbrew
(https://github.com/utahta/pythonbrew).

If you prefer you can force the usage (and installation) of a fresh pythonbrew
based python instance instead of the system python; just use:

.. code-block:: sh

  $ sh oms-core-installer.sh --target /opt/oms -- --brew

User accounts
-------------

Before starting we need at least an admin user account:

.. code-block:: sh

  $ bin/passwd -a john -g admins

You can change the password later on with the same `bin/passwd` utility, see
`bin/passwd --help` for additional info.

Starting up
-----------

Then you can start oms daemon with:

.. code-block:: sh

  $ cd oms
  $ bin/omsd

Connecting
----------

You can connect to the OMS console via ssh:

.. code-block:: sh

  $ ssh john@localhost -p 6022


Plugins
-------

You can install plugins with:

.. code-block:: sh

  $ bin/plugin install opennode.oms.knot

Uninstall with:

.. code-block:: sh

  $ bin/plugin uninstall opennode.oms.knot

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

If you are developing a plugin you'll want to install the plugin in "Development mode". This means
that the OMS core daemon will run using your plugin *from a source checkout*.

You have to pass the directory containing the plugin sources checkout:

.. code-block:: sh

  $ bin/plugin install opennode.oms.knot -d ../opennode-knot


Installing a development plugin which depends on another plugin will fetch the dependency as egg:

.. code-block:: sh

  $ bin/plugin list
  $ bin/plugin install opennode.oms.onc -d ../opennode-console-exp
  ...
  $ bin/plugin list
  opennode.oms.knot (0.0-5-gd425) [autodep]
  opennode.oms.onc (0.0-320-gc5ca) [dev]

Once a plugin has been installed as egg dependency, you can "upgrade" it to dev mode by simply installing it again with the `-d` switch:

.. code-block:: sh

  $ bin/plugin list
  $ bin/plugin install opennode.oms.knot -d ../opennode-knot
  ...
  $ bin/plugin list
  opennode.oms.knot (0.0-5-gd425) [dev]
  opennode.oms.onc (0.0-320-gc5ca) [dev]

Pitfalls when setting up on Ubuntu
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Since v2.0.0 OMS requires Salt instead of Certmaster/Func to function.

Make sure that VMs have the latest opennode-tui installed:

.. code-block:: sh

    root@on-vm $ yum -y update opennode-tui
