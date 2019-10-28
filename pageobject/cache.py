import logging
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import StaleElementReferenceException

page_logger = logging.getLogger('PageObject')


class CachedElement(object):

    def __init__(self, elements, context_hash):
        self.elements = elements
        self.context_hash = context_hash

    def is_stale(self, context_hash):
        # if the context HTML of the element is changed, the elemnet will be discarded
        # this may be caused by some pure front end JS without changing the "._id" of the context
        # it this case the cache (indexed by "._id" and selctor) will hit but the content saved is stale potentially
        if context_hash != self.context_hash:
            return True

        try:
            # if element(s) is/are disabled or invisible, they will be regarded as stale
            # this may happen on some overlay component of which the visibility/accessibility is set on a very top level of the DOM
            # in this case the changing container is outside of the vision of the context
            if isinstance(self.elements, WebElement):
                stale = not self.elements.is_enabled() or not self.elements.is_displayed()
            elif type(self.elements) is list:
                stale = any([not e.is_enabled() or not e.is_displayed() for e in self.elements])
            elif type(self.elements) is dict:
                stale = False
                for es in self.elements.values():
                    if isinstance(es, WebElement):
                        stale = not es.is_enabled() or not es.is_displayed()
                    else:
                        stale = any([not e.is_enabled() or not e.is_displayed() for e in es])
        except StaleElementReferenceException:
            # a StaleElementReferenceException surely indicates the element is stale
            # notice that any element get stale in data structure will invalid the whole container
            return True
        else:
            return stale


class PageElementCache(object):
    def __init__(self, page):
        self._page = page
        self._current_page_id = self._html_identifier()
        self._cache = {}

    def _html_identifier(self):
        return self._page.find_element_by_tag_name('html')._id

    def write(self, context_id, context_hash, selector, elements):
        # the key of the cache is the context ID and the selector of the web element
        # the value saved in the cache is the saved data structure of web elements
        # the data structure depends on the user of the cache
        #   - PageElement: single element
        #   - PageElementTemplate: single element
        #   - PageElements: array of elements
        #   - PageElementDict: dict of elements

        page_logger.debug('Writing to cache')
        if self.page_stale:
            page_logger.debug('Page is stale, clear cache and continue')
            self.reset()
        self._cache[context_id, selector] = CachedElement(elements, context_hash)

    def read(self, context_id, context_hash, selector):
        # cache is accessed by using the context_id and the selector
        page_logger.debug('Reading from cache')
        if self.page_stale:
            page_logger.debug('Page is stale, returning None')
            self.reset()
            return None

        elements = self._cache.get((context_id, selector), None)
        if elements is None:
            page_logger.debug('Cache missid.')
            return None

        page_logger.debug('Cached element found.')
        if elements.is_stale(context_hash):
            page_logger.debug('Element is stale, discard and return None')
            self.remove(context_id, selector)
            return None
        return elements.elements

    def remove(self, context_id, selector):
        self._cache.pop((context_id, selector), None)

    @property
    def page_stale(self):
        # cache outdate when the internal _id of the <html> tag changes, this indicates a refresh or loaded a new page
        return self._html_identifier() != self._current_page_id

    def reset(self):
        page_logger.debug('Reset page ID to newest and clear cache')
        self._current_page_id = self._html_identifier()
        self._cache = {}
