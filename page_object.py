
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

    def __init__(self, loc, by=None, component=None, timeout=30):
        self.locator = loc
        self.by = by
        self.component = component
        self.timeout = timeout

    def __get__(self, instance, owner):
        """Getting a PageElement will return the element"""
        page_logger.debug('Accessing page element {}'.format(self.locator))
        loc = self._locator(instance)
        try:
            e = self._find_element(instance.context, loc)
            if self.component:
                e = self.component(e)
            return e
        except Exception as ex:
            page_logger.debug('Cannot find the element')
            page_logger.debug(str(ex))
            return None

    def __set__(self, instance, value):
        """Setting a PageElement will send keybord input to the element"""
        page_logger.debug('Setting page element')
        loc = self._locator(instance)
        element = self._find_element(instance.context, loc)
        self._set_element(element, value)

    def _locator(self, instance):
        by = self.by or instance.__default_by__ or By.ID
        return by, self.locator

    def _find_element(self, driver, loc):
        """Wait element appear and fetch element"""
        WebDriverWait(driver, self.timeout).until(EC.visibility_of_element_located(loc))
        element = driver.find_element(*loc)
        page_logger.debug('Element found: {}'.format(self.locator))
        return element

    @staticmethod
    def _select(element, value):
        page_logger.debug('Changing element to Select')
        element = Select(element)
        page_logger.debug('Selecting {}'.format(value))
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
        page_logger.debug('Entering {}'.format(value))
        element.clear()
        element.send_keys(str(value))

    def _set_element(self, element, value):
        element_type = element.get_attribute('type')
        getattr(self, '_' + element_type, self._input)(element, value)


class PageComponent(object):

    __default_by__ = None

    def __init__(self, element):
        self.context = element
        self.b = PageObject(element._parent)

    def __getattr__(self, name):
        # delegate to unresolvables webdriver
        return getattr(self.context, name)


class PageObject(object):
    """
    Base class for all page object.
    All attributes access and method calls not defined in the PageObject will
    be delegated to the webdriver.
    """

    __default_by__ = None

    wait_ajax_script = {
        'JQUERY': 'return jQuery.active == 0;',
        'ASP.NET': 'return Sys.WebForms.PageRequestManager.getInstance().get_isInAsyncPostBack() == false;'
    }

    def __init__(self, drv):
        self.context = drv

    def __getattr__(self, name):
        # delegate to unresolvables webdriver
        return getattr(self.context, name)

    def wait(self, condition, timeout):
        WebDriverWait(self.context, timeout).until(condition)

    def alert(self, timeout=5):
        """Wait and return alert"""
        page_logger.debug('Switching to alert.')
        self.wait(EC.alert_is_present())
        return self.context.switch_to.alert

    def window(self, windown, next_page, timeout=30):
        script = 'return document.readyState == "complete"'
        page_logger.debug('Switching to window[{}].'.format(windown))
        if type(windown) is int:
            windown = self.context.window_handles[windown]
        self.context.switch_to.window(windown)
        self.wait(lambda driver: driver.execute_script(script), timeout)
        return self.goto(next_page)

    def frame(self, frame, next_page):
        page_logger.debug('Switching to Frame[{}]'.format(frame))
        self.context.switch_to.frame(frame)
        return self.goto(next_page)

    def wait_ajax(self, lib='JQUERY', timeout=30):
        """Run AJAX call and wait for returning"""
        page_logger.debug('Waiting for AJAX using {}'.format(lib))
        js = self.wait_ajax_script.get(lib, 'return true;')
        self.wait(lambda driver: driver.execute_script(js), timeout)

    def goto(self, next_page):
        """
        Move to the next page.
        next_page - the full path to the page defined in a globally visible module.
        The reason for using a string instead of a class is to avoid circular importing
        """
        page_logger.debug('Changing page to <{}>'.format(next_page))
        path, cls = next_page.rsplit('.', 1)
        m = import_module(path)
        cls = getattr(m, cls)
        return cls(self.context)


class PageTable(PageComponent):

    __row_locator__ = ('', '')
    __row_component__ = None

    def __getitem__(self, index):
        row = self._all_rows()[index]
        return self.__row_component__(row)

    def __len__(self):
        return len(self._all_rows())

    def _all_rows(self):
        return self.context.find_elements(*self.__row_locator__)

    def query(self, once=False, **conditions):
        page_logger.debug('Querying table...')
        rows = self._all_rows()
        result = []

        for k, v in conditions.items():
            if not callable(v):
                conditions[k] = lambda x, ref=v: x.get_attribute('textContent') == ref

        for i, row in enumerate(rows):
            page_logger.debug('Checking row {}...'.format(i))

            if self.__row_component__:
                row = self.__row_component__(row)

            if not conditions or all(cond(getattr(row, attr)) for (attr, cond) in conditions.items()):
                page_logger.debug('Found matching row: {}'.format(i))
                result.append(row)
            else:
                page_logger.debug('No match.')

            if result and once:
                page_logger.debug('Terminating immediately after found.')
                return result[0]

        page_logger.debug('Found {} rows'.format(len(result)))
        if once and not result:
            return None
        else:
            return result
