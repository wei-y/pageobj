
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
    def __init__(self, loc, by=None, component=None, timeout=30):
        self.locator = loc
        self.by = by
        self.component = component
        self.timeout = timeout

    def __get__(self, instance, owner):
        loc = self._locator(instance)
        page_logger.debug('Accessing page element {}'.format(loc))
        try:
            e = self._find_element(instance.context, loc)
            if self.component:
                e = self.component(e, instance)
            return e
        except Exception as ex:
            page_logger.debug('Cannot find the element')
            page_logger.debug(str(ex))
            return None

    def __set__(self, instance, value):
        loc = self._locator(instance)
        page_logger.debug('Setting page element: {}'.format(loc))
        element = self._find_element(instance.context, loc)
        self._set_element(element, value)

    def _locator(self, instance):
        by = self.by or By.ID
        return by, self.locator

    def _find_element(self, driver, loc):
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
        if element.tag_name == 'select':
            self._select(element, value)
        else:
            element_type = element.get_attribute('type')
            getattr(self, '_' + element_type, self._input)(element, value)


class PageElements(PageElement):
    def __get__(self, instance, owner):
        loc = self._locator(instance)
        page_logger.debug('Accessing page elements: {}'.format(loc))
        try:
            es = self._find_elements(instance.context, loc)
            if self.component:
                es = map(self.component, [(e, instance) for e in es])
            return es
        except Exception as ex:
            page_logger.debug('Cannot find the element')
            page_logger.debug(str(ex))
            return None

    def __set__(self, instance, value):
        if type(value) is str:
            value = [value]
        try:
            value = (v for v in value)
        except TypeError:
            value = [value]
        loc = self._locator(instance)
        page_logger.debug('Setting page element: {}'.format(loc))
        elements = self._find_elements(instance.context, loc)
        map(self._set_element, [(e, v) for (e, v) in zip(elements, value)])

    def _find_elements(self, driver, loc):
        WebDriverWait(driver, self.timeout).until(EC.visibility_of_element_located(loc))
        element = driver.find_element(*loc)
        page_logger.debug('Element found: {}'.format(self.locator))
        return element


class PageComponent(object):
    def __init__(self, element, page):
        self.context = element
        self.page = page

    def __getattr__(self, name):
        return getattr(self.context, name)


class PageObject(object):
    _wait_ajax_script = {
        'JQUERY': 'return jQuery.active == 0;',
        'ASP.NET': 'return Sys.WebForms.PageRequestManager.getInstance().get_isInAsyncPostBack() == false;'
    }

    def __init__(self, drv):
        self.context = drv

    def __getattr__(self, name):
        return getattr(self.context, name)

    def wait(self, condition, timeout=30):
        WebDriverWait(self.context, timeout).until(condition)

    def alert(self, timeout=5):
        page_logger.debug('Switching to alert.')
        self.wait(EC.alert_is_present())
        return self.context.switch_to.alert

    def window(self, window, timeout=30):
        script = 'return document.readyState == "complete"'
        page_logger.debug('Switching to window[{}].'.format(window))
        if type(window) is int:
            window = self.context.window_handles[window]
        self.context.switch_to.window(window)
        self.wait(lambda driver: driver.execute_script(script), timeout)

    def frame(self, frame, next_page):
        page_logger.debug('Switching to Frame[{}]'.format(frame))
        self.context.switch_to.frame(frame)

    def wait_ajax(self, lib='JQUERY', timeout=30):
        page_logger.debug('Waiting for AJAX using {}'.format(lib))
        js = self._wait_ajax_script.get(lib, 'return true;')
        self.wait(lambda driver: driver.execute_script(js), timeout)

    def goto(self, next_page, window=None, frame=None, timeout=30):
        if window is not None:
            self.window(window)
        if frame is not None:
            self.frame(frame)
        return self.changepage(next_page, self.context)

    @staticmethod
    def changepage(next_page, drv):
        page_logger.debug('Changing page to <{}>'.format(next_page))
        path, cls = next_page.rsplit('.', 1)
        m = import_module(path)
        cls = getattr(m, cls)
        return cls(drv)


class PageTable(PageComponent):

    _row_locator = ('', '')
    _row_component = None

    def __getitem__(self, index):
        row = self._all_rows()[index]
        if self._row_component:
            return self._row_component(row, self.page)
        else:
            return row

    def __len__(self):
        return len(self._all_rows())

    def _all_rows(self):
        return self.context.find_elements(*self._row_locator)

    def query(self, once=False, **conditions):
        page_logger.debug('Querying table...')
        rows = self._all_rows()
        result = []

        for k, v in conditions.items():
            if not callable(v):
                conditions[k] = lambda x, ref=v: x.get_attribute('textContent') == ref

        for i, row in enumerate(rows):
            page_logger.debug('Checking row {}...'.format(i))

            if self._row_component:
                row = self._row_component(row, self.page)

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


class WaitPageLoaded(object):

    def __init__(self, page, timeout=30):
        self.page = page
        self.timeout = 30

    def __enter__(self):
        page_logger.debug('Entering wait...')
        self.old = self.page.find_element_by_tag_name('html').id

    def __exit__(self, *args):
        page_logger.debug('Exiting wait...')
        self.page.wait(lambda drv, old=self.old: old != self.page.find_element_by_tag_name('html').id, self.timeout)
        new = self.page.find_element_by_tag_name('html').id
        page_logger.debug('Page changed: old[{}] => new[{}]'.format(self.old, new))
        self.page.wait(lambda drv: drv.execute_script('return document.readyState == "complete";'), self.timeout)
        page_logger.debug('Page completed.')
