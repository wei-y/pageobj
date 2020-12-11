from .pageobject import PageElement, PageObject, PageComponent


def nextpage(name):
    """
    Defines the next page of an action.

    Args:
        name: the full package path to the class name of the next page. It can be a string, a dict or a callable.
            1) When it is a string, it is the full package path of the class name of the expected next page.
            In this case, the method being decorated must return None.
            2) When it is a dict, the key in the dict is the short token of next page and the value is teh package
            path to the class name of next page. The method being decorated must return one of the token to get to
            the page. This option provides a dynamic next page ability
            3) When it is a callable, it takes the return value of the decorated and returns the full package name to
            the class of next page. The method being decorated can return anything accepteble to the `name` parameter.

    Raises:
        RuntimeError: When type of name is not string, dict or callable
        RuntimeError: When next page name is not a string
        TypeError: When the context is neither `PageObject` nor `PageComponent`

    Returns:
        The wrapper to change the page class.
    """
    def wrapper(action):
        # action is the function defined in page object to be called and decorated
        # at the moment when it is decorated, it is a unbound method
        # it is called wrapped in the following `change_page` with the first argument set to `instance` representing
        # the item binding to the method
        def change_page(instance, *args, **kargs):
            # token is returned from the function and it is used to select which page to change to
            token = action(instance, *args, **kargs)

            if type(name) is str:
                # only one possible target page is defined, use it and ignore the returned token
                page_name = name
            elif type(name) is dict:
                # target pages are defined in a dict, use token as key
                default = name.get('__default__')
                page_name = name.get(token, default)
            elif callable(name):
                # target pages are defined as callable, use toke as input to the callable and return value as target
                page_name = name(token)
            else:
                msg = f'Parameter type to nextpage() must be string/dict/fuction. Value: {name}, Type: {type(name)}'
                raise RuntimeError(msg)

            if type(page_name) is not str:
                raise RuntimeError(
                    'Next page class must be a string, got: {} of type {}'.format(page_name, type(page_name)))

            if not (isinstance(instance, PageObject) or isinstance(instance, PageComponent)):
                raise TypeError('Instance is not PageObject or PageComponent')

            # create a new page object using the target page object class and webdriver
            p = instance.page.changepage(page_name, instance.page.context)

            # call the on_enter() hook when changed to a new page
            if hasattr(p, 'on_enter'):
                p.logger.debug('Running entering hook of {}'.format(page_name))
                p.on_enter()
            return p
        return change_page
    return wrapper


def pageconfig(default_by=None, timeout=0):
    """
    Setup `PageObject` with default attributes

    Args:
        default_by (str, optional): the default type of locators in this page. Defaults to None.
        timeout (int, optional): the default value of timeout when waiting. Defaults to 0.

    Returns:
        The wrapper to inject attributes to class definition
    """
    def wrapper(c):
        # inject attributes to the class decorated
        for attr in c.__dict__.values():
            if isinstance(attr, PageElement) and default_by and not attr.by:
                attr.by = default_by
        if timeout:
            c._timeout = timeout
        return c
    return wrapper


def tableconfig(row_locator=None, row_component=None, column_locator=None):
    """
    Setup `PageTable` configurations

    Args:
        row_locator (tuple, optional): a locator in Selenium format to find rows in the context of the table.
            Defaults to None.
        column_locator (tuple, optional): a locator in Selemium format to find column in the context of the table.
            Defaults to None. The locator needs to be a string template that can be solidified to by column name.
        row_component (class, optional): the class of the row component. Defaults to None.

    Returns:
        The wrapper to inject attributes to class definition
    """
    def wrapper(c):
        if row_locator:
            c._row_locator = row_locator
        if row_component:
            c._row_component = row_component
        if column_locator:
            c._column_locator = column_locator
        return c
    return wrapper
