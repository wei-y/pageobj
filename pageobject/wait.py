import logging
import inspect
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import traceback
import re

page_logger = logging.getLogger('PageObject')

"""
There are two different kind of timeout values: the one set on PageElement, and the one set in pageconfig for pages and components
These two does not share any common usage scenarios.

-- Time out of PageElement and its sub-classes:
When fetching an element, it can wait the element to be availabe before action. The timeout setting on PageElement is used here to
guard this process from waiting infinitely. If the timeout is not set (default to 0), it fetches the element immediately without waiting.

-- Time out of Page and Component
The timeout value set on PageObject or PageComponent by pageconfig() is used as a default wait value for all wait_*() operations defined in the wait module.
For a page, it will always use the timeout value set on the page class or any of its base classes.
For a component, it will try to find timeout value on itself, if it is not set (value of 0), then it will grab the value from the page containing the component.
If the value is not set, it will default to 0, which means all waitings will expire immediately.
Note that component defined in deeper level of the page structure will also only try itself and the page. All the intermediate components are ignored regarding
to finding timeout value.
The pattern to use this is to set a safe timeout value on the most general level of page inheritance. Adjust it specificly when needed and share the
general settings for the majority of pages/components.
"""

class BaseWaitAfter(object):
    """
    Abstract class for waiting after an action. It is used in a `with` block.
    """

    def __init__(self, context, timeout=0, ignore_timeout=False):
        """Initialize a Wait object"""
        self.context = context
        self._timeout = timeout
        self.ignore_timeout = ignore_timeout

    def __enter__(self):
        """Abstract method called before an action"""
        pass

    def __exit__(self, *args):
        """
        Steps called after an action. It calls the abstract `_exit_action()` which is implemented in sub-classes
        It intecept `TimeoutException` if `ignore_timeout` is set. Otherwise it will raise the exception to the caller.
        """
        try:
            self._exit_action()
        except Exception as e:
            if isinstance(e, TimeoutException) and self.ignore_timeout:
                page_logger.debug('Timeout when waiting...')
                page_logger.debug(traceback.format_exc())
            else:
                raise e

    @property
    def timeout(self):
        return self._timeout or self.context.timeout

    def _element(self, name):
        """Looking for an element defined in the inheritence hierarchy by name"""
        for base in inspect.getmro(self.context.__class__):
            page_logger.debug('Looking for {} in {}'.format(name, base.__name__))
            e = base.__dict__.get(name, None)
            if e:
                return e
        return None


class WaitPageLoadedAfter(BaseWaitAfter):
    """
    Wait for page to be loaded after an action.

    It compares the internal `id` property of WebElement representing <html> before and after the operation.
    After the `id` is changed, it waits until `document.readyState` is complete.
    """

    def __enter__(self):
        """Read `id` of <html> before action"""
        try:
            self.old = self.context.find_element_by_tag_name('html').id
        except NoSuchElementException:
            self.old = None

    def _exit_action(self, *args):
        """Compoare `id` of <html> until it is change, then wait for `document.readyState` to be complete"""
        self.context.wait(lambda drv, old=self.old: old != self.context.find_element_by_tag_name('html').id,
                          self.timeout)
        new = self.context.find_element_by_tag_name('html').id
        page_logger.debug('Page changed: old[{}] => new[{}]'.format(self.old, new))
        self.context.wait(lambda drv: drv.execute_script('return document.readyState == "complete";'), self.timeout)
        page_logger.debug('Page completed.')


class WaitElementDisplayedAfter(BaseWaitAfter):
    """
    Wait an element to display after an operation. There is not enter action for this scenario.
    After action, it waits until the element exists in DOM and displayed.
    """
    def __init__(self, context, element_name, timeout=0, ignore_timeout=False):
        """Initialize the wait object. save the name of the element"""
        super(WaitElementDisplayedAfter, self).__init__(context, timeout, ignore_timeout)
        self.element_name = element_name

    def _exit_action(self, *args):
        """Wati until the element is in the DOM and visually displayed"""
        e = self._element(self.element_name).locator
        ctx = self.context
        page_logger.debug('Waiting element to display: {} "{}"'.format(self.element_name, str(e)))
        self.context.wait(lambda drv: getattr(ctx, self.element_name, None) and getattr(ctx, self.element_name).is_displayed(), self.timeout)
        page_logger.debug('Element displayed.')


class WaitElementDisappearedAfter(BaseWaitAfter):
    """
    Wait an element to disappear after an operation. There is not enter action for this scenario.
    After action, it waits until the element disappears from the DOM or visually hidden.
    """
    def __init__(self, context, element_name, timeout=0, ignore_timeout=False):
        """Initialize the wait object. save the name of the element"""
        super(WaitElementDisappearedAfter, self).__init__(context, timeout, ignore_timeout)
        self.element_name = element_name

    def _exit_action(self, *args):
        """Wait until the element is removed from DOM or visually hidden"""
        def _disappeared(drv, ctx=self.context, name=self.element_name):
            e = getattr(ctx, name)
            try:
                if not e:
                    return True
                elif not e.is_displayed():
                    return True
                else:
                    return False
            except StaleElementReferenceException:
                page_logger.debug('Element is changing, check in next round...')
                page_logger.debug(traceback.format_exc())
                return False

        e = self._element(self.element_name).locator
        page_logger.debug('Waiting element to disappear: {} "{}"'.format(self.element_name, str(e)))
        self.context.wait(_disappeared, self.timeout)
        page_logger.debug('Element disappeared.')


class WaitElementChangedAfter(BaseWaitAfter):
    """
    Wait an element to change after an operation. It uses the internal WebElement `id` to decide when an element is changed.
    """
    def __init__(self, context, element_name, timeout=0, ignore_timeout=False):
        """Initialize the wait object. save the context and name of the element"""
        super(WaitElementChangedAfter, self).__init__(context, timeout, ignore_timeout)
        e = self._element(element_name)
        self.locator = e.by or By.ID, e.locator

    def __enter__(self):
        """Find the element and save its id"""
        try:
            self.old = self.context.find_element(*self.locator).id
        except NoSuchElementException as e:
            page_logger.debug('Element does not exist.')
            page_logger.debug(traceback.format_exc())
            self.old = None

    def _exit_action(self, *args):
        """Wait until id is changed"""
        self.context.wait(lambda drv: self.old != self.context.find_element(*self.locator).id, self.timeout)
        new = self.context.find_element(*self.locator).id
        page_logger.debug('Element changed: old[{}] => new[{}]'.format(self.old, new))


class WaitAJAXAfter(BaseWaitAfter):
    """
    Wait for an AJAX call to be finished. It uses different Javascript snippet to check asynch call status.
    It support Jquery and ASP.net at the moment.
    """
    _wait_ajax_after_script = {
        'JQUERY': 'return jQuery.active == 0;',
        'ASP.NET': 'return Sys.WebForms.PageRequestManager.getInstance().get_isInAsyncPostBack() == false;'
    }

    def __init__(self, context, lib='JQUERY', timeout=0, ignore_timeout=False):
        """Initialize the wait object."""
        super(WaitAJAXAfter, self).__init__(context, timeout, ignore_timeout)
        self.lib = lib

    def _exit_action(self, *args):
        """Wait until the status checking script returns True"""
        page_logger.debug('Waiting for AJAX using {}'.format(self.lib))
        js = self._wait_ajax_after_script.get(self.lib, 'return true;')
        self.context.wait(lambda driver: driver.execute_script(js), self.timeout)
        page_logger.debug('AJAX done.')


class WaitHTTPRequestAfter(BaseWaitAfter):
    """
    Wati for an HTTP request to be finished. It waits until the specified URL pattern is responded for a given
    number of time.
    """
    def __init__(self, context, url_pattern, counter=1, timeout=0, ignore_timeout=False):
        """Initialize the wait object."""
        super(WaitHTTPRequestAfter, self).__init__(context, timeout, ignore_timeout)
        self.clear_buffer = 'window.performance.clearResourceTimings();'
        self.get_url_entries = 'return window.performance.getEntriesByType("resource");'
        self.url_pattern = re.compile(url_pattern)
        self.counter = counter
        self.urls = {}

    def _get_matching_url_entries(self):
        """Read all entries of the matching URL access"""
        entries = self.context.execute_script(self.get_url_entries)
        return dict((e['startTime'], e['name']) for e in entries if self.url_pattern.match(e['name']))

    def _wait_urls(self, drv):
        """Wait until the specified URL is visited for a given number times"""
        new_entries = self._get_matching_url_entries()
        page_logger.debug('Matching URL access after operation: {}'.format(str(new_entries)))
        for k in self.urls:
            if k in new_entries:
                new_entries.pop(k)
        return len(new_entries) >= self.counter

    def __enter__(self):
        page_logger.debug('Waiting for {} request(s) to URL {}'.format(self.counter, self.url_pattern))
        self.context.execute_script(self.clear_buffer)
        self.urls = self._get_matching_url_entries()
        page_logger.debug('Matching URL access before operation: {}'.format(str(self.urls)))

    def _exit_action(self):
        self.context.wait(self._wait_urls, self.timeout)
        page_logger.debug('URL access condition matched.')


class WaitMixin(object):
    """
    Wait functions mixin to PageObject. All wait funcitons are collected here as a mixin class.
    This class is not supposed to be standalone, it must be mixed into PageObject.
    """

    # By default, timeout value is 0 for all PageObject. It must be set explicitly at a base level
    # of the page definition.
    _timeout = 0

    @property
    def timeout(self):
        """Try to use the timeout value of the component first, then the timeout value of the page"""
        return self._timeout or self.page._timeout

    def wait(self, condition, timeout=0, ignore_timeout=False):
        """
        A general wait function wrapping WebDriverWait.until. It will intercept TimeoutException when
        ignore_timeout is set. Otherwise exceptions are thrown to caller.

        Args:
            condition (callable): the condition to wait for. See WebDriverWait.unitl for details
            timeout (int, optional): timeout value. Defaults to 0.
            ignore_timeout (bool, optional): If True, trap the TimeoutException, otherwise throw the exception to the caller. Defaults to False.

        Raises:
            e: any excetption raised by WebDriverWait.until
        """
        page_logger.debug('Waiting for conditions...')
        try:
            WebDriverWait(self.page, timeout or self.timeout).until(condition)
        except TimeoutException as e:
            if ignore_timeout:
                page_logger.debug('Timeout when waiting...')
                page_logger.debug(traceback.format_exc())
            else:
                raise e

    def wait_page_loaded_after(self, timeout=0, ignore_timeout=False):
        """
        Wait page loaded after an action. It is supposed to be used in a `wait` block.

        Args:
            timeout (int, optional): timeout value. Defaults to 0.
            ignore_timeout (bool, optional): If True, trap the TimeoutException, otherwise throw the exception to the caller. Defaults to False.

        Returns:
            Wait object handling the wait context.
        """
        return WaitPageLoadedAfter(self.page, timeout, ignore_timeout)

    def wait_element_displayed_after(self, element_name, timeout=0, ignore_timeout=False):
        """
        Wait element to display after an action. It is supposed to be used in a `wait` block.

        Args:
            element_name (str): the name of the element in question
            timeout (int, optional): timeout value. Defaults to 0.
            ignore_timeout (bool, optional): If True, trap the TimeoutException, otherwise throw the exception to the caller. Defaults to False.

        Returns:
            Wait object handling the wait context.
        """
        return WaitElementDisplayedAfter(self, element_name, timeout, ignore_timeout)

    def wait_element_disappeared_after(self, element_name, timeout=0, ignore_timeout=False):
        """
        Wait element to disappear after an action. It is supposed to be used in a `wait` block.

        Args:
            element_name (str): the name of the element in question
            timeout (int, optional): timeout value. Defaults to 0.
            ignore_timeout (bool, optional): If True, trap the TimeoutException, otherwise throw the exception to the caller. Defaults to False.

        Returns:
            Wait object handling the wait context.
        """
        return WaitElementDisappearedAfter(self, element_name, timeout, ignore_timeout)

    def wait_element_changed_after(self, element_name, timeout=0, ignore_timeout=False):
        """
        Wait element to change after an action. It is supposed to be used in a `wait` block.

        Args:
            element_name (str): the name of the element in question
            timeout (int, optional): timeout value. Defaults to 0.
            ignore_timeout (bool, optional): If True, trap the TimeoutException, otherwise throw the exception to the caller. Defaults to False.

        Returns:
            Wait object handling the wait context.
        """
        return WaitElementChangedAfter(self, element_name, timeout, ignore_timeout)

    def wait_ajax_after(self, lib='JQUERY', timeout=0, ignore_timeout=False):
        """
        Wait AJAX call to finish after an action. It is supposed to be used in a `wait` block.

        Args:
            lib (str): the AJAX call initiator, can be 'JQUERY' or 'ASP.NET'. default to 'JQUERY'
            timeout (int, optional): timeout value. Defaults to 0.
            ignore_timeout (bool, optional): If True, trap the TimeoutException, otherwise throw the exception to the caller. Defaults to False.

        Returns:
            Wait object handling the wait context.
        """
        return WaitAJAXAfter(self.page, lib, timeout, ignore_timeout)

    def wait_http_request_after(self, url_pattern, counter=1, timeout=0, ignore_timeout=False):
        """
        Wait http request to be responded for a given number of times after an action. It is supposed to be used in a `wait` block.

        Args:
            url_pattern (str): the URL regex pattern to be matched
            count (int, optional): the number of times for the URL to be visited. Defaults to 1
            timeout (int, optional): timeout value. Defaults to 0.
            ignore_timeout (bool, optional): If True, trap the TimeoutException, otherwise throw the exception to the caller. Defaults to False.

        Returns:
            Wait object handling the wait context.
        """
        return WaitHTTPRequestAfter(self.page, url_pattern, counter, timeout, ignore_timeout)
