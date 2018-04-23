
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select
from selenium.webdriver.support import expected_conditions as EC
from importlib import import_module
import logging


page_logger = logging.getLogger('PageObject')
page_logger.setLevel(logging.DEBUG)
fh = logging.FileHandler('pageobject.log', "w")
formatter = logging.Formatter('%(name)s: %(message)s')
fh.setFormatter(formatter)
page_logger.addHandler(fh)


class PageSchema(object):
    """
    Base class for locators definition
    """

    _default_by = By.ID
    _timeout = 30


class Locator(object):

    def __init__(self, locator, by=None, wrapper=None):
        self.by = by
        self.locator = locator
        self.wrapper = wrapper


class PageMeta(type):
    """
    Meta class for the PageObject.
    This class will load the configuration in __scheme__ to be Page Element.
    """

    def __new__(cls, name, bases, attrs):
        page_logger.debug('Installing locators to <%s>' % name)
        # __scheme__ refers to the a class inherited from PageScheme
        page_schema = attrs.get('__schema__')
        if page_schema:
            # fetch all Locator defined in the scheme
            locs = (a for a in page_schema.__dict__.items() if isinstance(a[1], Locator))
            for lname, loc in locs:
                # Use default_by if loc.by is not defined
                loc.by = page_schema._default_by if not loc.by else loc.by
                # Create a PageElement as an attribute in the Page class
                attrs[lname] = PageElement(loc, page_schema._timeout)
                page_logger.debug('%s...' % lname)
        page_logger.debug('Installation done <%s>' % name)
        return type.__new__(cls, name, bases, attrs)


class PageObject(object):
    """
    Base class for all page object.
    All attributes access and method calls not defined in the PageObject will
    be delegated to the webdriver.
    """

    __metaclass__ = PageMeta
    wait_ajax_script = {
        'JQUERY': 'return jQuery.active == 0;',
        'ASP.NET': 'return Sys.WebForms.PageRequestManager.getInstance().get_isInAsyncPostBack() == false;'
    }

    def __init__(self, drv):
        self.driver = drv

    def __getattr__(self, name):
        # delegate to unresolvables webdriver
        return getattr(self.driver, name)

    def alert(self, timeout=5):
        """Wait and return alert"""
        page_logger.debug('Switching to alert.')
        WebDriverWait(self.driver, timeout).until(EC.alert_is_present())
        return self.driver.switch_to.alert

    def wait_ajax(self, lib='JQUERY', timeout=30):
        """Run AJAX call and wait for returning"""
        page_logger.debug('Waiting for AJAX using %s' % lib)
        js = self.wait_ajax_script.get(lib, 'return true;')
        WebDriverWait(self.driver, timeout).until(
            lambda driver: driver.execute_script(js))

    def goto(self, next_page):
        """
        Move to the next page.
        next_page - the full path to the page defined in a globally visible module.
        The reason for using a string instead of a class is to avoid circular importing
        """
        page_logger.debug('Changing page to <%s>' % next_page)
        path, cls = next_page.rsplit('.', 1)
        m = import_module(path)
        cls = getattr(m, cls)
        return cls(self.driver)

    @staticmethod
    def set_element(element, value):
        """
        Set value directly to element:
        select: choose option of the value
        checkbox: tick/untick according to value
        radio: select if value is True
        other: assume text, clear and input value as string
        """
        element_type = element.get_attribute('type')
        if element.tag_name == 'select':
            # Select element needs to be converted to Select object
            page_logger.debug('Changing element to Select')
            element = Select(element)
            page_logger.debug('Selecting %s' % value)
            element.select_by_visible_text(value)
        elif element_type == 'checkbox':
            # Checkbox element accepts Boolean value and only change when needed
            if element.is_selected() is not value:
                element.click()
        elif element_type == 'radio':
            # Radio element accepts Boolean True only
            if value is True:
                element.click()
        else:
            # All other elements are treated as input/text
            page_logger.debug('Entering %s' % value)
            element.clear()
            element.send_keys(str(value))


class PageElement(object):
    """
    PageElement are used inside a PageObject to define elements on the page.
    """

    def __init__(self, loc, timeout=30):
        self.locator = loc.by, loc.locator
        self.wrapper = loc.wrapper
        self.timeout = timeout

    def __get__(self, instance, owner):
        """Getting a PageElement will return the element"""
        page_logger.debug('Accessing page element {}'.format(self.locator))
        try:
            e = self._find_element(instance.driver)
            if self.wrapper is not None:
                e = self.wrapper(e)
            return e
        except Exception:
            page_logger.debug('Cannot find the element')
            return None

    def __set__(self, instance, value):
        """Setting a PageElement will send keybord input to the element"""
        page_logger.debug('Setting page element')
        element = self._find_element(instance.driver)
        PageObject.set_element(element, value)

    def _find_element(self, driver):
        """Wait element appear and fetch element"""
        WebDriverWait(driver, self.timeout).until(EC.visibility_of_element_located(self.locator))
        element = driver.find_element(*self.locator)
        page_logger.debug('Element found: %s' % self.locator[1])
        return element


class TableMeta(type):
    """
    Meta class for Table.
    This class will solidify all columns selectors into cls._columns
    """

    def __new__(cls, name, bases, attrs):
        page_logger.debug('Installing columns to table <%s>' % name)
        _columns = {}
        for n, attr in attrs.items():
            if not isinstance(attr, TableColumn):
                continue
            page_logger.debug('%d %s...' % (attr.index, n))
            attr.name = n
            _columns[attr.index] = attr
        attrs['_columns'] = _columns
        page_logger.debug('Installation done <%s>' % name)
        return type.__new__(cls, name, bases, attrs)


class TableColumn(object):
    """
    Define a table column.
    index - the index of the cells find by the locator of Table.__cell__, start from 0
    wrapper - a callable used to cook data from the element located by index
    """

    def __init__(self, index, wrapper=None):
        self.name = ''
        self.index = index
        self.wrapper = wrapper

    def fetch(self, e):
        page_logger.debug('Fetching cell from row...')
        if self.wrapper is not None:
            page_logger.debug('Wrapping table cell...')
            return self.wrapper(e)
        else:
            return e


class TableRow(object):
    """
    A row in the table located by Table.__row__
    """

    def __init__(self, element, cell_loc, clmn_spec):
        self.element = element
        self.cell_loc = cell_loc
        self.clmn_spec = clmn_spec

    def __getattr__(self, name):
        page_logger.debug('Getting cell by name: %s' % name)
        cells = self.element.find_elements(*self.cell_loc)
        page_logger.debug('%d cells located' % len(cells))
        for i, c in enumerate(cells):
            if self.clmn_spec[i].name == name:
                return self.clmn_spec[i].fetch(c)
        page_logger.debug('Not found.')
        return None

    def __getitem__(self, index):
        page_logger.debug('Getting cell by index: %d' % index)
        if index in self.clmn_spec:
            cells = self.element.find_elements(*self.cell_loc)
            page_logger.debug('%d cells located' % len(cells))
            return self.clmn_spec[index].fetch(cells[index])
        page_logger.debug('Not found')
        return None

    def __str__(self):
        cells = self.element.find_elements(*self.cell_loc)
        text = []
        for i, c in self.clmn_spec.items():
            text.append(str(self.clmn_spec[i].fetch(cells[i])))
        return ' | '.join(text)


class TableBase(object):
    """
    The base class of Table.
    This class will convert a <table> element into a structured data table
    """

    __metaclass__ = TableMeta

    def __init__(self, table):
        page_logger.debug('Table created.')
        self.table = table

    def __getitem__(self, index):
        page_logger.debug('Getting row %d' % index)
        rows = self.table.find_elements(*self.__row__)
        return TableRow(rows[index], self.__cell__, self._columns)

    def __len__(self):
        return len(self.table.find_elements(*self.__row__))

    def search(self, once=False, **conditions):
        """
        A Generator yielding all matching rows
        """
        page_logger.debug('Searching table...')
        for k, v in conditions.items():
            if not callable(v):
                conditions[k] = lambda x, ref=v: x.get_attribute('contentText') == ref

        for i in range(len(self)):
            page_logger.debug('Checking row %d...' % i)
            if not conditions:
                page_logger.debug('No conditions supplied. Match.')
                yield self[i]

            if all((getattr(self[i], name) is not None and
                    condition(getattr(self[i], name))
                   for name, condition in conditions.items())):
                page_logger.debug('Found matching row: %d' % i)
                yield self[i]
                if once:
                    page_logger.debug('Terminating immediately after found.')
                    break

            # match = True
            # for name, condition in conditions.items():
            #     page_logger.debug('Checking %s...' % name)
            #     e = getattr(self[i], name)
            #     if e is None or not condition(e):
            #         page_logger.debug('Failed')
            #         match = False
            #         break
            # if match:
            #     page_logger.debug('Found matching row: %d' % i)
            #     yield self[i]
            #     if once:
            #         page_logger.debug('Terminating immediately after found.')
            #         break
