Security
========

Permission model
----------------

OMS permission model tries to be friendly with those who are familiar with the unix permission model, nevertheless
it offers several enhancements.

Each object has a list of Access Control Entries (ACE), called Access Control List (ACL).

An ACE is composed of a `principal`, a `mode`  and a `permission`.

A `principal` is either an user or a group.

The `mode` can be either *Allow* or *Deny*

The possible permissions are:

    #) `read` (**r**) the principal can get the value(s) object

    #) `write` (**w**) the principal can perform modification of the object

    #) `execute` (**x**) the principal can perform actions on the object

    #) `delete` (**d**) the principal can delete the object

    #) `view` (**v**) the principal can see that the object exists, but not necessary get it's value(s)

    #) `admin` (**a**) the principal can do everything on the object

The ACL of an object can be viewed with the `getfacl` command:

.. code-block:: sh

  user@oms:/# getfacl /
  user:john:+vr
  user:john:-wd

This means that the user `john` has two `Allow` ACEs, one allowing the `view` permission and the other allowing the `read` permission,
and two `Deny` ACEs, one denying the `write` permission and the other denying the `delete` permission.

`Deny` ACEs take precedence over `Allow` permissions, declared in the object or inherited from the parents.

The ACL can be manipulated with the `setfacl` command:

.. code-block:: sh

  user@oms:/# setfacl / -m u:john:vr -d u:john:wd
  user@oms:/# getfacl /
  user:john:+vr
  user:john:-wd

  user@oms:/# setfacl / -x u:john:d -m u:john:d -d u:john:r
  user@oms:/# getfacl /
  user:john:+vd
  user:john:-r

In order to appreciate the difference between adding a denial with a  `Deny` ACE (with `-d`) 
vs removing an entry with an `Allow` ACE (with `-x`), we have to take a closer look at permission inheritance.

Permission inheritance
----------------------


Rights
------

The OMS permissions define a set of **rights** which are more fine grained and depend on the actual object being secured.
Examples of OMS permission `rights` are as `@read`, `@rest`, `@poweroff`, ...
Some rights (like `@read`) might have the same name as the permission, but they are not the same concept.

`Rights` allow us to define the exact meaning of a given permission, and to fine-tune what can be actually done by principals
having a given permission.

The mapping between a `permission` and it's `rights` is defined globally in the `oms_roles` file and this mapping can be extended on a per-type basis.

You can even override the mapping between a `permission` and it's `rights` for a particular object instance, e.g you can revoke the grant `@shutdown` to
those who have `write` permission on a given Compute object, while retaining all the existing rights associated with `write` (e.g. access the console etc).

