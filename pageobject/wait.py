import logging
import inspect
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import traceback

page_logger = logging.getLogger('PageObject')
global_timeout = 10


class BaseWait(object):
    def __init__(self, context, timeout=None, ignore_timeout=False):
        self.context = context
        self._timeout = timeout
        self.ignore_timeout = ignore_timeout

    def __enter__(self):
        pass

    def __exit__(self, *args):
        try:
            self._exit_action()
        except Exception as e:
            if isinstance(e, TimeoutException) and self.ignore_timeout:
                page_logger.warn('Timeout when waiting...')
                page_logger.warn(traceback.format_exc(e))
            else:
                raise e

    @property
    def timeout(self):
        return self._timeout or self.context.timeout

    def _element(self, name):
        for base in inspect.getmro(self.context.__class__):
            page_logger.debug('Looking for {} in {}'.format(name, base.__name__))
            e = base.__dict__.get(name, None)
            if e:
                return e
        return None


class WaitPageLoaded(BaseWait):
    def __enter__(self):
        self.old = self.context.find_element_by_tag_name('html').id

    def _exit_action(self, *args):
        self.context.wait(lambda drv, old=self.old: old != self.context.find_element_by_tag_name('html').id,
                          self.timeout)
        new = self.context.find_element_by_tag_name('html').id
        page_logger.debug('Page changed: old[{}] => new[{}]'.format(self.old, new))
        self.context.wait(lambda drv: drv.execute_script('return document.readyState == "complete";'), self.timeout)
        page_logger.debug('Page completed.')


class WaitElementDisplayed(BaseWait):
    def __init__(self, context, element_name, timeout=None, ignore_timeout=False):
        super(WaitElementDisplayed, self).__init__(context, timeout, ignore_timeout)
        self.element_name = element_name

    def _exit_action(self, *args):
        e = self._element(self.element_name).locator
        ctx = self.context
        page_logger.debug('Waiting element to display: {}'.format(str(e)))
        self.context.wait(lambda drv: getattr(ctx, e, None) and getattr(ctx, e).is_displayed(), self.timeout)
        page_logger.debug('Element displayed.')


class WaitElementDisappeared(BaseWait):
    def __init__(self, context, element_name, timeout=None, ignore_timeout=False):
        super(WaitElementDisappeared, self).__init__(context, timeout, ignore_timeout)
        self.element_name = element_name

    def _exit_action(self, *args):
        e = self._element(self.element_name).locator
        ctx = self.context
        page_logger.debug('Waiting element to disappear: {}'.format(str(e)))
        self.context.wait(lambda drv: not getattr(ctx, e, None) or not getattr(ctx, e).is_displayed(), self.timeout)
        page_logger.debug('Element disappeared.')


class WaitElementChanged(BaseWait):
    def __init__(self, context, element_name, timeout=None, ignore_timeout=False):
        super(WaitElementChanged, self).__init__(context, timeout, ignore_timeout)
        e = self._element(element_name)
        self.locator = e.by or By.ID, e.locator

    def __enter__(self):
        try:
            self.old = self.context.find_element(*self.locator).id
        except NoSuchElementException as e:
            page_logger.warn('Element does not exist.')
            page_logger.warn(traceback.format_exc(e))
            self.old = None

    def _exit_action(self, *args):
        self.context.wait(lambda drv: self.old != self.context.find_element(*self.locator).id, self.timeout)
        new = self.context.find_element(*self.locator).id
        page_logger.debug('Element changed: old[{}] => new[{}]'.format(self.old, new))


class WaitAJAX(BaseWait):
    _wait_ajax_script = {
        'JQUERY': 'return jQuery.active == 0;',
        'ASP.NET': 'return Sys.WebForms.PageRequestManager.getInstance().get_isInAsyncPostBack() == false;'
    }

    def __init__(self, context, lib='JQUERY', timeout=None, ignore_timeout=False):
        super(WaitAJAX, self).__init__(context, timeout, ignore_timeout)
        self.lib = lib

    def _exit_action(self, *args):
        page_logger.debug('Waiting for AJAX using {}'.format(self.lib))
        js = self._wait_ajax_script.get(self.lib, 'return true;')
        self.context.wait(lambda driver: driver.execute_script(js), self.timeout)
        page_logger.debug('AJAX done.')


class WaitMixin(object):
    _timeout = None

    @property
    def timeout(self):
        return self._timeout or global_timeout

    def wait(self, condition, timeout=None, ignore_timeout=False):
        try:
            WebDriverWait(self.page, timeout or self.timeout).until(condition)
        except TimeoutException as e:
            if ignore_timeout:
                page_logger.warn('Timeout when waiting...')
                page_logger.warn(traceback.format_exc(e))
            else:
                raise e

    def wait_page_loaded(self, timeout=None, ignore_timeout=False):
        return WaitPageLoaded(self.page, timeout, ignore_timeout)

    def wait_element_displayed(self, element_name, timeout=None, ignore_timeout=False):
        return WaitElementDisplayed(self, element_name, timeout, ignore_timeout)

    def wait_element_disappeared(self, element_name, timeout=None, ignore_timeout=False):
        return WaitElementDisappeared(self, element_name, timeout, ignore_timeout)

    def wait_element_changed(self, element_name, timeout=None, ignore_timeout=False):
        return WaitElementChanged(self, element_name, timeout, ignore_timeout)

    def wait_ajax(self, lib='JQUERY', timeout=None, ignore_timeout=False):
        return WaitAJAX(self.page, lib, timeout, ignore_timeout)
