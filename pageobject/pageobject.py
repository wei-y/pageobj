
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import TimeoutException
from importlib import import_module
import logging
import traceback
import inspect

from wait import WaitMixin, global_timeout


page_logger = logging.getLogger('PageObject')
page_logger.setLevel(logging.DEBUG)
fh = logging.FileHandler('pageobject.log', "w")
formatter = logging.Formatter('%(name)s[%(levelname)s]: %(message)s')
fh.setFormatter(formatter)
page_logger.addHandler(fh)


class PageElement(object):
    def __init__(self, loc, by=None, component=None, value_only=False, ignore_visibility=False, timeout=None):
        self.locator = loc
        self.by = by
        self.component = component
        self.value_only = value_only
        self._timeout = timeout
        self.ignore_visibility = ignore_visibility

    def __get__(self, instance, owner):
        page_logger.debug('Accessing web element {}'.format(self._locator))
        try:
            e = self._find_element(instance, self._locator)
            if self.component:
                return self.component(e, instance)
            elif self.value_only:
                return self._get_element(e)
            else:
                return Select(e) if e.tag_name == 'select' else e
        except Exception as ex:
            page_logger.warn('Cannot find the element')
            page_logger.warn(traceback.format_exc(ex))
            return None

    def __set__(self, instance, value):
        page_logger.debug('Setting web element: {}'.format(self._locator))
        element = self._find_element(instance, self._locator)
        self._set_element(element, value)

    def timeout(self, instance):
        return self._timeout or instance._timeout or global_timeout

    @property
    def _locator(self):
        return self.by or By.ID, self.locator

    def _find(self, instance, loc, func):
        driver = instance.context
        try:
            WebDriverWait(driver, self.timeout(instance)).until(EC.visibility_of_element_located(loc))
        except TimeoutException as e:
            if self.ignore_visibility:
                page_logger.warn('Timeout when waiting element visible, ignore the error and try to operate on the element')
                page_logger.warn(traceback.format_exc(e))
            else:
                raise e
        element = func(*loc)
        page_logger.debug('Element found: {}'.format(self.locator))
        return element

    def _find_element(self, instance, loc):
        return self._find(instance, loc, instance.find_element)

    def _get_element(self, element):
        actions = dict(
            select=lambda e: Select(e).first_selected_option.text,
            checkbox=lambda e: e.is_selected(),
            radio=lambda e: e.is_selected(),
            input=lambda e: e.get_attribute('value'),
            textarea=lambda e: e.get_attribute('value'),
            default=lambda e: e.get_attribute('textContent').strip(),
        )
        act = 'select' if element.tag_name == 'select' else element.get_attribute('type')
        return actions.get(act, actions['default'])(element)

    def _set_element(self, element, value):
        actions = dict(
            select=lambda e, v: Select(e).select_by_visible_text(v),
            checkbox=lambda e, v: e.click() if e.is_selected() is not v else None,
            radio=lambda e, v: e.click() if v else None,
            default=lambda e, v: (e.clear(), e.send_keys(str(value)))
        )
        act = 'select' if element.tag_name == 'select' else element.get_attribute('type')
        actions.get(act, actions['default'])(element, value)


class PageElements(PageElement):
    def __get__(self, instance, owner):
        page_logger.debug('Accessing web elements: {}'.format(self._locator))
        try:
            es = self._find_elements(instance, self._locator)
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
        page_logger.debug('Setting web element: {}'.format(self._locator))
        elements = self._find_elements(instance, self._locator)
        [self._set_element(e, v) for (e, v) in zip(elements, value)]

    def _find_elements(self, instance, loc):
        return self._find(instance, loc, instance.find_elements)


class PageBase(WaitMixin):
    def __init__(self, context, page):
        self.context = context
        self.page = page

    def __getattr__(self, name):
        return getattr(self.context, name)


class PageComponent(PageBase):
    def __init__(self, element, page):
        super(PageComponent, self).__init__(element, page)


class PageObject(PageBase):
    def __init__(self, drv):
        super(PageObject, self).__init__(drv, self)

    def alert(self, timeout=None):
        page_logger.debug('Switching to alert.')
        self.wait(EC.alert_is_present(), timeout or self.timeout)
        return self.context.switch_to.alert

    def window(self, window, timeout=None):
        script = 'return document.readyState == "complete"'
        page_logger.debug('Switching to window[{}].'.format(window))
        if type(window) is int:
            window = self.context.window_handles[window]
        self.context.switch_to.window(window)
        self.wait(lambda driver: driver.execute_script(script), timeout or self.timeout)

    def frame(self, frame, next_page):
        page_logger.debug('Switching to Frame[{}]'.format(frame))
        self.context.switch_to.frame(frame)

    def goto(self, next_page, window=None, frame=None, timeout=None):
        if window is not None:
            self.window(window, timeout)
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
        return self._row_component(row, self.page) if self._row_component else row

    def __len__(self):
        return len(self._all_rows())

    def _all_rows(self):
        return self.context.find_elements(*self._row_locator)

    def query(self, once=False, **conditions):
        page_logger.debug('Querying table with conditions: {}...'.format(str(conditions)))
        rows = self._all_rows()
        result = []

        for k, v in conditions.items():
            if not callable(v):
                def cond(x, ref=v):
                    t = (x.get_attribute('textContent') if isinstance(x, WebElement) else x).strip()
                    page_logger.debug('value[{}] == expected[{}]? => {}'.format(t, ref, t == ref))
                    return t == ref
            else:
                def cond(x, c=v):
                    result = c(x)
                    page_logger.debug('value[{}] matching [{}]? => {}'.format(x, inspect.getsource(c).strip()[:50], result))
                    return result
            conditions[k] = cond
                # conditions[k] = lambda x, ref=v: \
                #     (x.get_attribute('textContent') if isinstance(x, WebElement) else x).strip() == ref

        for i, row in enumerate(rows):
            page_logger.debug('Checking row {}...'.format(i))

            if self._row_component:
                row = self._row_component(row, self.page)

            if not conditions or all(cond(getattr(row, attr)) for (attr, cond) in conditions.items()):
                page_logger.debug('Found matching row: {}'.format(i))
                result.append(row)

            if result and once:
                page_logger.debug('Terminating immediately after found.')
                return result[0]

        page_logger.debug('Found {} row(s)'.format(len(result)))
        return None if once and not result else result
