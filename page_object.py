
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException
from importlib import import_module
import logging


page_logger = logging.getLogger('PageObject')
page_logger.setLevel(logging.DEBUG)
fh = logging.FileHandler('pageobject.log', "w")
formatter = logging.Formatter('%(name)s: %(message)s')
fh.setFormatter(formatter)
page_logger.addHandler(fh)


class Locator(object):
    '''
    Thin wrapper of the raw Selenium locator
    '''

    def __init__(self, locator, by=None):
        # fall back to PageScheme._default_by if `by` is None
        self.by = by
        self.locator = locator


class PageScheme(object):
    '''
    Base class for locators collection of a page
    This class will only contain class attributes as locators
    Locators in this class will be installed into a PageObject class as attributs
    '''

    _default_by = By.ID     # Default to ID if BY is not defined in a locator
    _timeout = 30           # Timeout is 30s by default to find an element


class PageElement(object):
    """
    PageElement are used inside a PageObject to define elements on the page.
    """

    def __init__(self, loc, timeout=30):
        self.locator = loc.by, loc.locator
        self.timeout = timeout

    def __get__(self, instance, owner):
        """Getting a PageElement will return the element"""
        return self._find_element(instance.driver)

    def __set__(self, instance, value):
        """Setting a PageElement will send keybord input to the element"""
        element = self._find_element(instance.driver)
        PageObject.set_element(element, value)

    def _find_element(self, driver):
        """Wait element appear and fetch element"""
        WebDriverWait(driver, self.timeout).until(
            lambda drv: drv.find_element(*self.locator))
        element = driver.find_element(*self.locator)
        return element


class PageMeta(type):
    '''
    Meta class of the PageObject.
    Install all locators defined in PageScheme as PageElement.
    PageScheme is found by attribute __scheme__.
    '''

    def __new__(cls, name, bases, attrs):
        page_scheme = attrs.get('__scheme__', None)
        if page_scheme:
            locs = (loc for loc in page_scheme.__dict__.items()
                    if isinstance(loc[1], Locator))
        for loc_name, loc in locs:
            if not loc.by:
                loc.by = page_scheme._default_by
            attrs[loc_name] = PageElement(loc, page_scheme._timeout)
        return type.__new__(cls, name, bases, attrs)


class PageObject(object):
    '''
    Base class for all page object.
    Undefined attribute will be first looked for in __scheme__
    If the attribute does not exist in __scheme__ then delegate it to webdriver
    '''

    __metaclass__ = PageMeta

    def __init__(self, drv):
        self.driver = drv

    def __getattr__(self, name):
        return getattr(self.driver, name)

    def alert(self, timeout=5):
        WebDriverWait(self.driver, timeout).until(
            lambda driver: EC.alert_is_present())
        return self.driver.switch_to.alert

    def goto(self, next_page):
        path, cls = next_page.rsplit('.', 1)
        m = import_module(path)
        cls = getattr(m, cls)
        return cls(self.driver)

    @staticmethod
    def set_element(element, value):
        element_type = element.get_attribute('type')
        if element.tag_name == 'select':
            sel = Select(element)
            sel.select_by_visible_text(value)
        elif element_type == 'checkbox':
            if element.is_selected() is not value:
                element.click()
        elif element_type == 'radio':
            if value is True:
                element.click()
        else:
            element.clear()
            element.send_keys(str(value))
