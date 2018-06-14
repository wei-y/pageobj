from pageobject import PageElement, PageObject, PageComponent


def nextpage(name):
    if type(name) is str:
        name = {0: name}

    def wrapper(f):
        def change_page(instance, *args, **kargs):
            r = f(instance, *args, **kargs)
            page_name = name[0] if r is None else name[r]
            if isinstance(instance, PageObject):
                drv = instance.context
            elif isinstance(instance, PageComponent):
                drv = instance.page.context
            else:
                raise TypeError('Instance is not PageObject or PageComponent')
            return PageObject.changepage(page_name, drv)
        return change_page
    return wrapper


def pageconfig(default_by=None, timeout=None):
    def wrapper(c):
        for attr in c.__dict__.values():
            if isinstance(attr, PageElement) and default_by and not attr.by:
                attr.by = default_by
        if timeout:
            c._timeout = timeout
        return c
    return wrapper


def tableconfig(row_locator=None, row_component=None):
    def wrapper(c):
        if row_locator:
            c._row_locator = row_locator
        if row_component:
            c._row_component = row_component
        return c
    return wrapper
