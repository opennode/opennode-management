Configuration
=============

OMS loads it's configuration from several places, in this order:

 * $OMS_MODULE_DIR/opennode-oms.conf (contains hard defaults, bundled with the code)
 * $OMS_INSTALL_DIR/opennode-oms.conf (contains site defaults, provided by installer)
 * /etc/opennode/opennode-oms.conf (contains site configuration)
 * ~/.opennode-oms.conf (contains site configuration, useful for non-system installation)
 * /etc/opennode/id_rsa(.pub) -- Contains SSH keys specific for OMS, used to authenticate OMS users on
   hardware nodes and separate OMS authentication from the user it is running as. If these files are absent,
   OMS user's home directory is checked for key pairs before falling back to password authentication.

The configuration files loaded after can override values defined in the ones loaded earlier.

.. include:: gen/config_ref.rst
