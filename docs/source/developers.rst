OMS Developers
==============

Debugger
--------

You can starts oms with enabled debugging either using `bin/omsd --debug some-password` or `bin/omsd --winpdb`

Overview
--------

OMS is built on top of Twisted, and relies heavily one the Zope Component library.

The OMS core provides:

 1. A hierarchical "Information System" (HIS), made persistent via ZODB. OMS components (e.g. plugins) define models
    that are instantiated in the HIS and can expose their functionality by providing data through attributes and streams,
    reacting on model attribute modifications and by directly exposing executable `actions`.

 2. Access to the HIS can be exposed via several interfaces, among whose there is a REST interface and a command-line interface called OMSH.

 3. The OMSH command-line interface provides a UNIX-like shell environment for advanced interaction with OMS objects in the HIS tree.
    Plugins can easily create new commands, with full declarative argument parsing and command line completion.
    It's is accessible via ssh or via web terminal emulation (ajax and/or websocket).

 4. The REST interface exposes read-write access to objects in the HIS tree, serialized as JSON.
    Components can customize their JSON rendering by defining model-specific `Views`.

 5. A security framework, based on fine grained ACLs with flexible rules and inheritance.

 6. A process model, including long running background processes called `daemons`.

 7. A synchronization mechanism which can import external entities and create OMS objects in the HIS representing them.

 8. An event framework which detects changes in models and spawns actions.


OMS tries to mimic familiar UNIX concepts whenever it makes sense; it can be seen as a "management operating system".

GIT guidelines
--------------

 1. Try to avoid cluttering the public history with unnecessary merge commits, i.e. always use `git pull --rebase` when pulling
    This can be easily achieved by setting a per-repository setting `git config branch.master.rebase true`, which and/or setting a global
    setting with `git config --global branch.autosetuprebase always` so that every new git clone will get this setting for free.

 2. If you are merging local branches before pull rebasing to master, it's always preferred to first pull rebase master on local master,
    then `git rebase master` in one of the feature branch, then `git rebase <lastbranch>` in each of the other branches, and finally
    merge in master (which should be a fast forward merge).

 3. Keep separate things in separate commits, i.e. use `git add -p` in order to split unrelated changes in separate commits,
    and interacitve rebase `git rebase -i` in order to curate (split/merge) commits before pushing it to the public repo.

 4. Ticket commit messages should point to the relevant ticket(s). The ticket number(s) should go in parethesis::

      Fixed minor rendering issue (ON-123)
      Improved handling of blabla (ON-123, ON-321)

 5. Ticket commit messages should start with a short description about what this change `did`, e.g. "Fixed a bug in...", "Cleaned up ..."

Security
--------

The OMS security model has two levels, one meant for end-users called `permissions`, and the other meant for component developers called
`rights`.

A `permission` can be granted to a principal, through various means, like an ACL on an object.
When a principal has a `permission` it also has the `rights` associated  with that permission.
The resulting `rights` granted to a principal are checked

A `permission` is associated with `rights` via domain specific configuration. The goal is to insulate the developer
from the OMS administrator, who can build rich scenarios from the existing components, and yet leave the security
model easy to manage both for the end user and the developer.

OMS models can have attributes, and each attribute is protected so that only principals having a given `right` can access it.
There is a separate right for reading the attribute and modifying it (Modification to lists are seen as modifications to the attribute).

For example let's consider modeling a user object:

The developer operates a first modeling decision when the attributes are declared, for example non sensitive attributes will require
the `@read` right for reading and `@modify` for changing it, while a password attribute might require a `@read_pwd` right
for reading but still a simple `@modify` right for changing it.

The modeling phase acknowledges that the password attribute is not meant to leak around, but doesn't mandate that this attribute is
implemented as write-only; after all, being a password attribute, it has to be checked during logins by some component, and we want to make
sure that component has the rights to perform that action.

However, during the modeling phase the developer isn't really interested in defining who is going to get the right to read the password hash
attribute. The modeler's job is simply to capture underlying differences in the meaning of the attributes and to group related attribute
according to the security domain they belong.

The modeler doesn't have to fear that doing so will yield a vast number of `rights`
which will confuse the end user or administrator, as specific configuration will reunite `rights` in order define a `permission`.

An example of a possible permissions-rights configuration:

The `read` permission will have the `@read`, `@vnc_connect`, ... rights, but the `admin` permission will have all them
and `@modify`, `@create`, ... but not `@read_pwd`, because being a admin user doesn't imply you have access to inner gear like the password hash.

Even if the admin user has the rights to modify this mapping and grant himself the `right` to read the password field, it still makes sense
to not have this right mapped in the `admin` permission by default. The reason has to do with the way the visibility of attribute is tied
to the securiy framework; more details in the next section.

Model and security
~~~~~~~~~~~~~~~~~~

Each access to the HIS performed by OMSH or REST will result in an object wrapped in a security proxy which will check all accesses to
attributes.

OMSH will filter out all data for which there are no rights to see. This doesn't meant that the user won't see objects
for those she hasn't read permission, because as we saw earlier there is a difference between permissions and rights.

Let's see an example: if the principal has no `@read_pwd` right,
then the password won't be shown in the object's rendering. The default behavior is to silently skip that attribute in the rendering
but if needed, the user can see which attributes are being skipped because of security issues because the model definition is public
and thus tools can use it to enumerate all the attributes.

But, if the principal has no rights to access the `__name__` attribute of a model, then the whole object disappears from a container
because there is usually no static way to enumerate the content of a container as it was the case with the model attributes.

In order to allow the possibility to have distinct permissions for reading an object or for simply seeing that it exists, the
`__name__` attribute  (inherited by every module) is declared with the `@view` right:

.. code-block:: python

   class Model(persistent.Persistent):
       implements(IModel, IAttributeAnnotatable)
       rights(dict(__name__='view'))

       __parent__ = None
       __name__ = None


So, if a scenario wants to expose fine grained view permission to the end user it will have  the following
permission->role mapping: `read` -> (`@read`) and `view` -> (`@view`)

If the scenario wants to simply hide all objects which are not readable
and avoid exposing an additional `view` permission: `read` -> (`@read`, `@view`)

And, if all unreadable objects are visible to everyone (only the name): `read` -> (`@read`) and `oms.nothing` -> (`@view`, ....)

We don't know which of these choices is better, it depends on the scenario for a given OMS based application, but the choice
is entirely described with the security framework, with no need for special handling nor special configuration to map to specific
scenario requirements.


Implementation details
~~~~~~~~~~~~~~~~~~~~~~

OMS permission are implemented with zope security `roles` while oms `rights` are implemented in terms of `zope security permissions`.

That can be a source of confusion, OMS core will take care about hiding this from end users and developers.
