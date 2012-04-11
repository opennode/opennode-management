Configuration
=============

OMS loads it's configuration from several places, in this order:

 * $OMS_MODULE_DIR/opennode-oms.conf (contains hard defaults, bundled with the code)
 * $OMS_INSTALL_DIR/opennode-oms.conf (contains site defaults, provided by installer)
 * /etc/opennode/opennode-oms.conf (contains site configuration)
 * ~/.opennode-oms.conf (contains site configuration, useful for non-system installation)

The configuration files loaded after can override values defined in the ones loaded earlier.

.. include:: gen/config_ref.rst
