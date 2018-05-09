
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


class PageElement(object):
    """
    PageElement are used inside a PageObject to define elements on the page.
    """

    def __init__(self, loc, by=By.ID, component=None, timeout=30):
        self.locator = loc
        self.by = by
        self.component = component
        self.timeout = timeout

    def __get__(self, instance, owner):
        """Getting a PageElement will return the element"""
        page_logger.debug('Accessing page element {}'.format(self.locator))
        try:
            e = self._find_element(instance.context)
            if self.component is not None:
                e = self.component(e)
            return e
        except Exception as ex:
            page_logger.debug('Cannot find the element')
            page_logger.debug(str(ex))
            return None

    def __set__(self, instance, value):
        """Setting a PageElement will send keybord input to the element"""
        page_logger.debug('Setting page element')
        element = self._find_element(instance.context)
        self._set_element(element, value)

    def _find_element(self, driver):
        """Wait element appear and fetch element"""
        loc = self.by, self.locator
        WebDriverWait(driver, self.timeout).until(EC.visibility_of_element_located(loc))
        element = driver.find_element(*loc)
        page_logger.debug('Element found: %s' % self.locator)
        return element

    @staticmethod
    def _select(element, value):
        page_logger.debug('Changing element to Select')
        element = Select(element)
        page_logger.debug('Selecting %s' % value)
        element.select_by_visible_text(value)

    @staticmethod
    def _checkbox(element, value):
        if element.is_selected() is not value:
            page_logger.debug('Clicking checkbox...')
            element.click()

    @staticmethod
    def _radio(element, value):
        page_logger.debug('Clicking radio button...')
        if value:
            element.click()

    @staticmethod
    def _input(element, value):
        page_logger.debug('Entering %s' % value)
        element.clear()
        element.send_keys(str(value))

    def _set_element(self, element, value):
        element_type = element.get_attribute('type')
        getattr(self, '_' + element_type, self._input)(element, value)


class PageComponent(object):

    def __init__(self, element):
        self.context = element
        self.page = PageObject(element._parent)

    def __getattr__(self, name):
        # delegate to unresolvables webdriver
        return getattr(self.context, name)


class PageObject(object):
    """
    Base class for all page object.
    All attributes access and method calls not defined in the PageObject will
    be delegated to the webdriver.
    """

    wait_ajax_script = {
        'JQUERY': 'return jQuery.active == 0;',
        'ASP.NET': 'return Sys.WebForms.PageRequestManager.getInstance().get_isInAsyncPostBack() == false;'
    }

    def __init__(self, drv):
        self.context = drv

    def __getattr__(self, name):
        # delegate to unresolvables webdriver
        return getattr(self.context, name)

    def alert(self, timeout=5):
        """Wait and return alert"""
        page_logger.debug('Switching to alert.')
        WebDriverWait(self.context, timeout).until(EC.alert_is_present())
        return self.context.switch_to.alert

    def wait_ajax(self, lib='JQUERY', timeout=30):
        """Run AJAX call and wait for returning"""
        page_logger.debug('Waiting for AJAX using %s' % lib)
        js = self.wait_ajax_script.get(lib, 'return true;')
        WebDriverWait(self.context, timeout).until(
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
        return cls(self.context)


class PageTable(PageComponent):

    __row_locator__ = ('', '')
    __row_component__ = None

    def __getitem__(self, index):
        row = self._all_rows()[index]
        return self.__row__['component'](row)

    def __len__(self):
        return len(self._all_rows())

    def _all_rows(self):
        return self.context.find_elements(*self.__row_locator__)

    def query(self, once=False, **conditions):
        page_logger.debug('Querying table...')
        rows = self._all_rows()

        for k, v in conditions.items():
            if not callable(v):
                conditions[k] = lambda x, ref=v: x.get_attribute('contentText') == ref

        for i, row in enumerate(rows):
            page_logger.debug('Checking row %d...' % i)

            if self.__row_component__:
                row = self.__row_component__(row)

            for a, c in conditions.items():
                page_logger.debug(getattr(row, a).get_attribute('contentText'))

            match = not conditions or all(cond(getattr(row, attr)) for (attr, cond) in conditions.items())

            if match:
                page_logger.debug('Found matching row: %d' % i)
                yield row
            else:
                page_logger.debug('No match.')

            if match and once:
                page_logger.debug('Terminating immediately after found.')
                break
