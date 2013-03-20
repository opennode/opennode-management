import martian


__all__ = ['permissions']


class permissions(martian.Directive):
    """Use this directive in a class in order to set its attribute permissions."""

    scope = martian.CLASS
    store = martian.ONCE
    default = None
