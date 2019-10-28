
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.common.action_chains import ActionChains
from importlib import import_module
import logging
import traceback

from .wait import WaitMixin
from .cache import PageElementCache


page_logger = logging.getLogger('PageObject')
page_logger.setLevel(logging.DEBUG)
fh = logging.FileHandler('pageobject.log', "w")
formatter = logging.Formatter('%(asctime)s %(pathname)s [%(levelname)s]: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
fh.setFormatter(formatter)
page_logger.addHandler(fh)


class PageElement(object):
    """
    The descriptor for a *single* DOM element in `PageObject` or `PageComponent`.

    Different configurations to the `PageElement` results in different values:

    - When reading a `PageElement`

      1. locate the element by the locator
      #. if component is not None, cast the element as specified `PageComponent` and use it as the value
      #. if component is None and value_only is True, get value from the element located directly (1_).
      #. if component is None and value_only is False, use the located element as value
      #. following any of the above steps, apply read_hook to the value if read_hook is not None, otherwise return value

    - When writing a `PageElement`, value_only has no effect

      1. locate the element by the locator
      #. if write_hook is None, set value to the element directly (2_)
      #. if write_hook is not None and component is None, apply write_hook to the element located
      #. if write_hook is not None and component is set, cast the element located as specified `PageComponent` and apply
         write_hook to it

    .. [1] Rules to get value from an element:

      - <checkbox>/<radio>: is_selected()
      - <input type="text">/<input type="url">/<input type="number">/<textarea>: "value" attribute
      - <select>: first_selected_option.text
      - all the other tags: "textContent" attribute

    .. [2] Rules to set value to an element:

      - <checkbox>/<radio>: click()
      - <select>: select_by_visible_text()
      - all ther other tags: clear() and send_keys()


    """

    def __init__(self, loc, by=None, component=None, value_only=False, ignore_visibility=False, timeout=0, read_hook=None, write_hook=None, enable_cache=False):
        """
        Create a new DOM element descriptor

        Args:
            loc (string): locator string of the DOM element in the current context

            by (string, optional): type of the locator. Defaults to None.
                Options to this field is the same as in selenium.webdriver.common.by.By. It will use default_by in
                `pageconfig` of the current context.
            component (Sub-class of `PageComponent`, optional): The component of the current DOM. Defaults to None.
                If a DOM element is a wrapper of a functional component, the component can be defined by another class
                inherited from `PageComponent`. Apart from locating the element, it is also cast as the component object.
            value_only (bool, optional): The descriptor returns the element value if True. Defaults to False.
                The element value is defined as following:
                - <checkbox>/<radio>: is_selected()
                - <input type="text">/<input type="url">/<input type="number">/<textarea>: "value" attribute
                - all the other tags: "textContent" attribute
                This field has no effect if "component" is set
            ignore_visibility (bool, optional): Defaults to False.
                If set to True, ignores visibility of the element and tries to operate on it, otherwise it will throw
                NoSuchElementException exception.
            timeout (int, optional): seconds to wait for the described element to be visible.
                Defaults to 0 which means no waiting.
            read_hook (callable, optional): a function to process the return of the descriptor. Defaults to None.
                The function must take two arguments (driver, element) and returns a value
            write_hook (callable, optional): a function to handle what happens when writing to an element.
                Defaults to None. The function must take three arguments (driver, element, value)
            enable_cache (bool, optional): Experiment feature to speed up finding elements. Defaults to False.
        """
        self.locator = loc
        self.by = by
        self.component = component
        self.value_only = value_only
        self._timeout = timeout
        self.ignore_visibility = ignore_visibility
        self.read_hook = read_hook
        self.write_hook = write_hook
        self.enable_cache = enable_cache

    def __get__(self, instance, owner):
        """Reading entrance to the descriptor. Return None if the element does not exist"""

        page_logger.debug('Accessing web element "{}": {}'.format(self.name, self._locator))
        try:
            element = self._read_cache(instance)
            if element is None:
                element = self._find_element(instance, self._locator)
                self._write_cache(instance, element)
            return self._convert_element(instance, element)
        except Exception:
            page_logger.debug('Cannot find the element')
            page_logger.debug(traceback.format_exc())
            return None

    def __set__(self, instance, value):
        """Write entrance to the descriptor. Raises NoSuchElement if element does not exist"""

        page_logger.debug('Setting web element: "{}": {} to  {}'.format(self.name, self._locator, value))
        element = self._read_cache(instance)
        if element is None:
            element = self._find_element(instance, self._locator)
        self._assign_element(instance, element, value)
        self._write_cache(instance, element)

    def __set_name__(self, owner, name):
        self.name = name

    def timeout(self, instance):
        return self._timeout

    @property
    def _locator(self):
        return self.by or By.ID, self.locator

    def _read_cache(self, instance, locator=None):
        # read cahced element by ccontext ID (None if context is a page) and the selector text
        # a specific locator different from self.locator can be passed in (sub-class PageElementTemplate uses this parameter)
        # cache is stored in the PageObject instance which is visible to any elements on the page
        if not self.enable_cache or not instance.page.enable_cache:
            return None
        context_id = None if isinstance(instance, PageObject) else instance._id
        try:
            context_hash = None if isinstance(instance, PageObject) else hash(instance.get_attribute('outerHTML'))
        except StaleElementReferenceException:
            page_logger.debug('Element context is stale, skipped reading from cache.')
            return
        locator = self._locator if locator is None else locator
        return instance.page.cache.read(context_id, context_hash, locator)

    def _write_cache(self, instance, element, locator=None):
        # write cahced element by ccontext ID (None if context is a page) and the selector text
        # a specific locator different from self.locator can be passed in (sub-class PageElementTemplate uses this parameter)
        # cache is stored in the PageObject instance which is visible to any elements on the page
        if not self.enable_cache or not instance.page.enable_cache:
            return
        context_id = None if isinstance(instance, PageObject) else instance._id
        try:
            context_hash = None if isinstance(instance, PageObject) else hash(instance.get_attribute('outerHTML'))
        except StaleElementReferenceException:
            page_logger.debug('Element context is stale, skipped writing to cache.')
            return
        locator = self._locator if locator is None else locator
        instance.page.cache.write(context_id, context_hash, locator, element)

    def _find(self, driver, instance, loc, func):
        """
        Wait for element to be visible then return the element(s).

        Args:
            driver (WebDriver): The webdriver instance currently used.
            instance (WebElement): The context of the current descriptor
            loc (tuple): Locator of the element
            func ([type]): Either webdriver.find_element or web_driver.find_elements

        Raises:
            TimeoutException: the element is not visible after timeout. It will not be raised when ignore_timeout is True.
            NoSuchElementException: the element does not exist when timeout is not spefified

        Returns:
            WebElement: The located web element
        """

        if self.timeout(instance) != 0:
            try:
                WebDriverWait(driver, self.timeout(instance)).until(EC.visibility_of_element_located(loc))
            except TimeoutException as e:
                if self.ignore_visibility:
                    page_logger.debug('Timeout when waiting element visible, ignore the error and try to operate on the element')
                    page_logger.debug(traceback.format_exc())
                else:
                    raise e
        try:
            element = func(*loc)
        except NoSuchElementException as e:
            page_logger.debug('Cannot find the element {}: {} on page'.format(self.name, loc))
            raise e
        page_logger.debug('Element found')
        return element

    def _find_element(self, instance, loc):
        return self._find(instance.context, instance, loc, instance.context.find_element)

    def _find_elements(self, instance, loc):
        return self._find(instance.context, instance, loc, instance.context.find_elements)

    def _convert_element(self, instance, e):
        """
        Convert a raw WebElement to a proper value.

        There are four possible return values of a web element:
          1. A component defined by the user
          #. The text/value of the element
          #. The raw WebElement object
          #. The value returned by read_hook, this can be applied after any of the above 3

        Args:
            instance (WebElement): The context of the current element
            e (WebElement): The raw WebElement to be converted

        Returns:
            Converted value of the WebElement
        """

        if self.component:
            result = self.component(e, instance.page)
        elif self.value_only:
            result = self._get_element(e)
        else:
            result = Select(e) if e.tag_name == 'select' else e
        if self.read_hook:
            result = self.read_hook(instance, result)
        return result

    def _assign_element(self, instance, e, value):
        """
        Set WebElement to a certain value.

        If write_hook is True, it will try convert the WebElement to `component` if specified,
        then apply write_hook to the element/component.
        If write_hook is False, it will apply the standard `_set_element` to the element.

        Args:
            instance (WebElement/WebDriver): Context of the current element
            e (WebElement): The WebElement to be set
            value: The value to be set to the WebElement
        """

        if self.write_hook:
            e = self.component(e, instance.page) if self.component else e
            self.write_hook(instance, e, value)
        else:
            self._set_element(e, value)

    def _get_element(self, element):
        """
        Default rule to get value from WebElement.
          - <select>: first selecte option text
          - <input type="radio">/<input type="checkbox">: is_selected()
          - <textarea>/<input type="text">/<input type="number">/<input type="url">: value attribute of the element
          - all the others: textContent attribute of the element

        Args:
            element (WebElement): The element to be read

        Returns:
            The value of the element
        """
        actions = {
            'select': lambda e: Select(e).first_selected_option.text,
            ('input', 'checkbox'): lambda e: e.is_selected(),
            ('input', 'radio'): lambda e: e.is_selected(),
            ('input', 'text'): lambda e: e.get_attribute('value'),
            ('input', 'number'): lambda e: e.get_attribute('value'),
            ('input', 'url'): lambda e: e.get_attribute('value'),
            'textarea': lambda e: e.get_attribute('value'),
            'default': lambda e: e.get_attribute('textContent').strip(),
        }
        tag = element.tag_name
        input_type = element.get_attribute('type') if tag == 'input' else None
        if tag in actions:
            act = tag
        elif input_type:
            act = ('input', input_type)
        else:
            act = 'default'
        return actions.get(act, actions['default'])(element)

    def _set_element(self, element, value):
        """
        Default rule to set value to WebElement.
          - <select>: select_by_visible_text()
          - <input type="checkbox">: click the element if value is different the is_selected()
          - <input type="radio">: click the element if value is True
          - all the others: clear() and then send_keys()

        Args:
            element (WebElement): The element to be set
            value: The value to be set to the element
        """
        actions = dict(
            select=lambda e, v: Select(e).select_by_visible_text(v),
            checkbox=lambda e, v: e.click() if e.is_selected() is not v else None,
            radio=lambda e, v: e.click() if v else None,
            default=lambda e, v: (e.clear(), e.send_keys(str(value)))
        )
        act = 'select' if element.tag_name == 'select' else element.get_attribute('type')
        actions.get(act, actions['default'])(element, value)


class PageElements(PageElement):
    """
    Similar to `PageElement` in most behaviours. The variation of this class is that it represents an array of elements
    located by using find_elements(). All configurations defined in __init__ of `PageElement` apply to each element in the array.

    When setting to this descriptor, it accepts different value types and behaves differently:
      - list/tuple: the list/tuple is zipped with elements located and set using the same rule as `PageElement`
      - dictionary: set elements at certain index to specified values. Keys of the dict are indexes and values are values to be set to
      - str/int: set *all* elements to the value passed in
    """

    def __get__(self, instance, owner):
        """
        Get an element array.

        It will return an array of elements grabbed using the same method as single element.
        If element cannot be found, it will return [].
        """

        page_logger.debug('Accessing web elements: "{}": {}'.format(self.name, self._locator))
        try:
            elements = self._read_cache(instance)
            if elements is None:
                elements = self._find_elements(instance, self._locator)
                self._write_cache(instance, elements)
            elements = [self._convert_element(instance, e) for e in elements]
            return elements
        except Exception:
            page_logger.debug('Cannot find the element')
            page_logger.debug(traceback.format_exc())
            return []

    def __set__(self, instance, value):
        """
        Set values to an array of elements.
          - set an element array to str/int will change all cells in the array to the value
          - set an element array to another array will change elements in corresponding index to the value
          - set an element array to a dict using integer as key will set elements in corresponding index to the value
          - non-integer index will first be changed to integer, discard if cannot change

        Raises:
            ValueError: if the value type is none of those listed aboved.
        """

        page_logger.debug('Setting web element: "{}": {} to  {}'.format(self.name, self._locator, value))
        elements = self._read_cache(instance)
        if elements is None:
            elements = self._find_elements(instance, self._locator)

        if type(value) in (list, tuple):
            [self._assign_element(instance, e, v) for (e, v) in zip(elements, value)]
        elif type(value) is dict:
            for k, v in value.items():
                try:
                    index = int(k)
                    self._assign_element(instance, elements[index], v)
                except ValueError:
                    page_logger.debug('Cannot change index to integer, value is disgarded, Key: {}, Value: {}'.format(k, v))
                except IndexError:
                    page_logger.debug('Index out of range for PageElements {}, Key: {}, Value: {}'.format(self.name, k, v))
                    continue
        elif type(value) in (int, str):
            [self._assign_element(instance, e, value) for e in elements]
        else:
            raise ValueError('The value is not supported by PageElement "{}" setting: {}'.format(self.name, str(value)))


class PageElementTemplate(PageElement):
    """
    Another variation to find element on page. This class provide a parameterized locator to find element dynamically.
    This class set the locator as a Python format string. Parameters can be passed in at runtime to find element on the fly.

    Reading this descriptor will return a function which requires paramters to solidify the locator. Calling the function
    will return the same result following the rule defined in `PageElement`.

    This descriptor must be set to a tuple of two with the first one as paramters to the locator and the second one as value.
    Element will be located by the parameterized locator and then following the rule in `PageElement` to set value to the element.
    """

    def _fetch_element(self, instance, owner, *parameters):
        """
        The actual function to locate and set an element. This function is wrapped and returned as the result of `PageElementTemplate`.

        Args:
            instance (WebDriver/WebElement): the context of the current element
            owner: the class context of the current element
            *paramters: paramters to the locator
        """

        page_logger.debug('Accessing web element "{}": {} with parameter {}'.format(self.name, self._locator, parameters))
        locator = self._locator[0], self._locator[1].format(*parameters)
        try:
            element = self._read_cache(instance, locator=locator)
            if element is None:
                element = self._find_element(instance, locator)
                self._write_cache(instance, element, locator=locator)
            return self._convert_element(instance, element)
        except Exception:
            page_logger.debug('Cannot find the element')
            page_logger.debug(traceback.format_exc())
            return None

    def __set__(self, instance, value):
        """
        Set element specified by the first element of passed in paramter and set its value to the second.

        Args:
            instance (WebDriver/WebElement): The context of the current element.
            value (tupe of two): Paramters to locator and value to be set. The first element is the locator and the second is the value.
        """
        loc_para = (value[0], ) if type(value[0]) is str else value[0]
        locator = self._locator[0], self._locator[1].format(*loc_para)
        page_logger.debug('Setting web element: "{}": {} to  {}'.format(self.name, locator, value))
        element = self._read_cache(instance, locator=locator)
        if element is None:
            element = self._find_element(instance, locator)
            self._write_cache(instance, element, locator=locator)
        self._assign_element(instance, element, value[1])

    def __get__(self, instance, owner):
        """
        Get `PageElementTemplate`. It will return a function to be parameterized instead of a solid elemnt.
        """
        return lambda *p: self._fetch_element(instance, owner, *p)


class PageElementsTemplate(PageElement):
    """
    A combination of `PageElements` ant `PageElementTemplate`. This descriptor can find elements in batch using a template.

    Similar to `PageElementTemplate`, the getter of this descriptor will return a function taking paramaters to solidify
    locator. Difference is , the function will return an array of elements, just like `PageElements`.

    Setting this descriptor is also similar to the setter of `PageElementTemplate`. A pair of key and value should be
    used as the right value of the assignment. The first element of the pair is the paramter to construct the locator
    and the second is the value to be set. It is the same as in `PageElements`
    """

    def _fetch_element(self, instance, owner, *parameters):
        """
        The actual function to locate and set elements. This function is wrapped and returned as the result of `PageElementTemplate`.

        Args:
            instance (WebDriver/WebElement): the context of the current element
            owner: the class context of the current element
            *paramters: paramters to the locator
        """

        page_logger.debug('Accessing web element "{}": {} with parameter {}'.format(self.name, self._locator, parameters))
        locator = self._locator[0], self._locator[1].format(*parameters)
        try:
            elements = self._read_cache(instance, locator=locator)
            if elements is None:
                elements = self._find_elements(instance, locator)
                self._write_cache(instance, elements, locator=locator)
            return [self._convert_element(instance, e) for e in elements]
        except Exception:
            page_logger.debug('Cannot find the element')
            page_logger.debug(traceback.format_exc())
            return []

    def __set__(self, instance, value):
        """
        Set element specified by the first element of passed in paramter and set its value to the second.

        Args:
            instance (WebDriver/WebElement): The context of the current element.
            value (tupe of two): Paramters to locator and value to be set. The first element is the locator and the second is the value.
        """
        # build the locator
        loc_para = (value[0], ) if type(value[0]) is str else value[0]
        locator = self._locator[0], self._locator[1].format(*loc_para)

        # find all elements by the locator
        page_logger.debug('Setting web element: "{}": {} to  {}'.format(self.name, locator, value))
        elements = self._read_cache(instance, locator=locator)
        if elements is None:
            elements = self._find_elements(instance, locator)
            self._write_cache(instance, elements, locator=locator)

        # set values to elements
        if type(value[1]) in (list, tuple):
            # an array of values are zipped to elements and stops whichever exhausts first
            [self._assign_element(instance, e, v) for (e, v) in zip(elements, value[1])]
        elif type(value[1]) is dict:
            # set value (value of dict) by index (key of dict) to element
            for k, v in value[1].items():
                try:
                    index = int(k)
                    self._assign_element(instance, elements[index], v)
                except ValueError:
                    # index is not an integer, log error and skip
                    page_logger.debug('Cannot change index to integer, value is disgarded, Key: {}, Value: {}'.format(k, v))
                    continue
                except IndexError:
                    # index out of range, log error and skip
                    page_logger.debug('Index out of range for PageElements {}, Key: {}, Value: {}'.format(self.name, k, v))
                    continue
        elif type(value[1]) in (int, str):
            # set an entire array of elements to a single value
            [self._assign_element(instance, e, value[1]) for e in elements]
        else:
            # unknown type of value.
            raise ValueError('The value is not supported by PageElement "{}" setting: {}'.format(self.name, str(value)))

    def __get__(self, instance, owner):
        """
        Get `PageElementTemplate`. It will return a function to be parameterized instead of a solid elemnt.
        """
        return lambda *p: self._fetch_element(instance, owner, *p)


class PageElementDict(PageElement):
    """
    A dictionary of elements on the page.

    This class organize elements on the page into a dictionary by defining how to find items, keys and values.
    The concept is to locate the whole container element of the dictionary first, then, in the context of the container,
    locate dictionary items. In the context of each item, it will locate key and value respectively and build a dictionary
    by located elements.

    When getting the descriptor, it will return a real dictionary containing all elements found thus all dictionary operations are valid.
    If multiple elements can be matched with the `value_loc`, all of them will be fetched and saved in an array. If only one value is
    found, it will be returned. If either key or value cannot be located in an item, the item will be ignored silently.

    Trying to use [] syntax to set element will only change the dictionary builtv when locating elements. The actual page will not be affected.
    The descriptor can only be set to a dictionary with keys as element keys to be changed and value as the value to be set.

    `PageElementDict` inherits from `PageElement` thus getting and setting elements follows the same rule in `PageElement`. All
    configurations defined in __init__ of `PageElement` apply to dictionary value. Keys are read using standard rule, or, if key_hook is defined,
    apply key_hook to the key elmenet to find the key. Parameters item_by, key_by, value_by are optional which will default to `loc`.

    """

    def __init__(self, loc, item_loc, key_loc, value_loc, by=None, item_by=None, key_by=None, value_by=None,
                 component=None, value_only=False, ignore_visibility=False, timeout=0, read_hook=None, write_hook=None, key_hook=None, enable_cache=False):
        """
        Initialize `PageElementDict` descriptor. It inherits `PageElement`.

        Args:
            loc (str): the locator of the whole dictionary container
            item_loc (str): the locator of a single item relative to the dictionary
            key_loc (str): the locator of the key relative to the item
            value_loc (str): the locator of the value relative to the item
            by (str, optional): type of the locator of the dictionary. Defaults to None which will use the `default_by` in `pageconfig`.
            item_by (str, optional): type of the locator of the item. Defaults to None which will use the value of `by`.
            key_by (str, optional): type of the locator of the key. Defaults to None which will use the value of `by`.
            value_by (str, optional): type of the locator of the value. Defaults to None which will use the value of `by`.
            key_hook (callable, optional): the hook applied to the key. Defaults to None.
            component (Sub-class of `PageComponent`, optional): The component of the current DOM. Defaults to None.
                If a DOM element is a wrapper of a functional component, the component can be defined by another class inherited from `PageComponent`.
                Apart from locating the element, it is also casted as the component object.
            value_only (bool, optional): The descriptor returns the element value if True. Defaults to False.
                The element value is defined as following:
                - <checkbox>/<radio>: is_selected()
                - <input type="text">/<input type="url">/<input type="number">/<textarea>: "value" attribute
                - all the other tags: "textContent" attribute
                This field has no effect if "component" is set
            ignore_visibility (bool, optional): Defaults to False.
                If set to True, ignores visibility of the element and tries to operate on it, otherwise it will throw NoSuchElementException exception.
            timeout (int, optional): seconds to wait for the described element to be visible. Defaults to 0 which means no waiting.
            read_hook (callable, optional): a function to process the return of the descriptor. Defaults to None.
                The function must take two arguments (driver, element) and returns a value
            write_hook (callable, optional): a function to handle what happens when writing to an element. Defaults to None.
                The function must take three arguments (driver, element, value)
        """
        super().__init__(loc, by, component, value_only, ignore_visibility, timeout, read_hook, write_hook)
        self._item_loc = item_loc
        self._key_loc = key_loc
        self._value_loc = value_loc
        self._item_by = item_by
        self._key_by = key_by
        self._value_by = value_by
        self.key_hook = key_hook

    def _loc(self, by, loc):
        return by or self.by or By.ID, loc

    @property
    def item_loc(self):
        return self._loc(self._item_by, self._item_loc)

    @property
    def key_loc(self):
        return self._loc(self._key_by , self._key_loc)

    @property
    def value_loc(self):
        return self._loc(self._value_by, self._value_loc)

    def _get_items(self, instance):
        """
        Find all items in the dictionary and return them as an array. Item are not separated into key and values at this point.

        Args:
            instance (WebDriver/WebElemet): the context of the current element

        Returns:
            list: a list of elements representing items in the array. An empty array will be returned if no element found
        """
        try:
            page_logger.debug('Fetching dict container: {}'.format(self._locator))
            dict_container = self._find_element(instance, self._locator)
            page_logger.debug('Fetching dict items: {}'.format(self.item_loc))
            items = self._find(dict_container, self, self.item_loc, dict_container.find_elements)
        except Exception:
            page_logger.debug('Cannot find element container/items')
            page_logger.debug(traceback.format_exc())
            items = []
        finally:
            return items

    def _get_key(self, instance, item):
        """
        Find key in an element.

        Args:
            instance (WebDriver/WebElemet): the context of the current element
            item (WebElement): the element represents the current item

        Returns:
            The key of the element found using the standard rule in `PageElement` or applying key_hook.
            Return None if key cannot be located
        """
        try:
            page_logger.debug('Fetching item key: {}'.format(self.key_loc))
            element = self._find(item, instance, self.key_loc, item.find_element)
            key = self.key_hook(instance, element) if self.key_hook else self._get_element(element)
            page_logger.debug('Got key {}'.format(key))
        except Exception:
            page_logger.debug('Cannot find element key')
            page_logger.debug(traceback.format_exc())
            key = None
        finally:
            return key

    def _get_value(self, instance, item):
        """
        Find values in an element. If multiple values are matched, all of them are saved in an array in the order of appearence in the DOM.

        Args:
            instance (WebDriver/WebElemet): the context of the current element
            item (WebElement): the element represents the current item

        Returns:
            A tuple. The first element are WebElement of values and the second is/are value(s) of the item
            Return ([], None) if value cannot be located
        """
        try:
            page_logger.debug('Fetching item value: {}'.format(self.value_loc))
            ves = self._find(item, instance, self.value_loc, item.find_elements)
            value = [self._convert_element(instance, ve) for ve in ves]
            value = value[0] if len(value) == 1 else value
            page_logger.debug('Got value {}'.format(value))
        except Exception:
            page_logger.debug('Cannot find the element value')
            page_logger.debug(traceback.format_exc())
            ves = []
            value = None
        finally:
            return ves, value

    def _set_value(self, instance, item, values):
        """
        Set value to an item in the dictionary. The value can be a list/tuple or a single value. If an array is provided, it will be
        zipped to each matching value element and set. If a single value is provided, it will be set to the first matching value element.

        Args:
            instance (WebDriver/WebElemet): the context of the current element
            item (WebElement): the element represents the current item
            values: value(s) to be set to the element
        """
        page_logger.debug('Setting item value: {}'.format(self.value_loc))
        ves = self._find(item, instance, self.value_loc, item.find_elements)
        target = values if len(ves) > 1 else [values]
        [self._assign_element(instance, atom, atom_value) for (atom, atom_value) in zip(ves, target)]

    def _get_cached_elements(self, instance, elements):
        """Experiment feature. Fetch element from cache."""
        result = {}
        for key, es in elements.items():
            value = [self._convert_element(instance, e) for e in es]
            value = value[0] if len(value) == 1 else value
            result[key] = value
        return result

    def _set_cached_elements(self, instance, elements, value):
        """Experiment feature. Save element to cache."""
        # set values of the cached dict
        # as the dict and keys are already stored, it only iterate over all values and set the cached elements accordingly
        # mismatched values are dropped silently
        for k, v in value.items():
            if k not in elements:
                continue
            if len(elements[k]) == 1:
                v = [v]
            [self._assign_element(instance, item, value) for (item, value) in zip(elements[k], v)]
        self._write_cache(instance, elements)
        return

    def __get__(self, instance, owner):
        """
        Fetch dictionary of elements. It will return a dictionary of element key and values.

        An empty dictionary will be returned if dictionary container cannot be located or items in the container cannot be located.
        """
        page_logger.debug('Accessing web elements: "{}": {}'.format(self.name, self._locator))
        page_logger.debug('Trying to build dict with item: {}, key: {}, value: {}'.format(self.item_loc, self.key_loc, self.value_loc))

        # try to get dict from cache
        cached = self._read_cache(instance)
        if cached is not None:
            return self._get_cached_elements(instance, cached)

        # cached missed, find elements on the page
        result = {}
        elements = {}
        items = self._get_items(instance)
        page_logger.debug('Found {} items'.format(len(items)))
        for i in items:
            key = self._get_key(instance, i)
            if key is None:
                continue
            ves, value = self._get_value(instance, i)
            if value is None:
                continue
            result[key] = value
            elements[key] = ves
            page_logger.debug('{} => {}'.format(key, value))

        # update cache with newest elements
        self._write_cache(instance, elements)
        return result

    def __set__(self, instance, value):
        """
        Set dictionary of elments. Note that it is NOT using the `[]` syntax due to limitation of descriptor.

        Values to be set must be a dictionary with keys matchting `PageElementDict` keys and values to be set.
        """
        page_logger.debug('Setting web elements: "{}": {} to  {}'.format(self.name, self._locator, value))
        page_logger.debug('Trying to set dict with item: {}, key: {}, value: {}'.format(self.item_loc, self.key_loc, self.value_loc))

        # try to use cached elements first
        elements = self._read_cache(instance)
        if elements is not None:
            self._set_cached_elements(instance, elements, value)
            return

        # cache missed, find elements on the page and set. "elements" is the dict to be stored in cache
        elements = {}
        items = self._get_items(instance)
        page_logger.debug('Found {} items'.format(len(items)))
        for i in items:
            key = self._get_key(instance, i)
            ves = self._get_value(instance, i)
            elements[key] = ves
            if key is None or key not in value:
                continue
            self._set_value(instance, i, value[key])
            page_logger.debug('Key matching, set element {} to {}'.format(key, value[key]))

        # update cache with newest result
        self._write_cache(instance, elements)


class PageBase(WaitMixin):
    """
    Base class of PageObject and PageComponent. This class will never be used directly and instantiated.
    Waiting function groups are mixed in by inheriting WaitMixin.
    """

    def __init__(self, context, page):
        """
        Initialize a `PageBase`.

        Args:
            context (PageBase): the parent context of the current object.
            page (WebDriver): the web drver driving the browser
        """
        self.context = context
        self.page = page

    def __getattr__(self, name):
        """
        Any undefined attributes are deligate to the wrapped WebDriver/WebElement.
        Attribute error will be raised if the attribute requested cannot be found.

        Args:
            name (str): name of the attribute requested

        Raises:
            AttributeError: in case that attribute cannot be found locally as well as in the wrapped WebDriver/WebElement

        Returns:
            The value of the attribute.
        """
        try:
            element = getattr(self.context, name)
        except AttributeError:
            raise AttributeError('Cannot find attribute {} in {}'.format(name, self.__class__.__name__))
        return element

    def hover(self, element):
        """
        Wrapper of ActionChain to hover over an element.

        Args:
            element (WebElement): the elment to be hovered over. It can be a web element descriptor that returns a WebElement or PageComponent
        """
        ac = ActionChains(self.page)
        ac.move_to_element(element).perform()

    def press_key(self, keys):
        """
        Wrapper of ActionChain to press keys to the whole page

        Args:
            keys (str): characters to be typed
        """
        ac = ActionChains(self.page)
        ac.send_keys(keys).perform()

    def double_click(self, element):
        """
        Wrapper to double click an element

        Args:
            element (WebElement): the element to be double clicked. It can be a web element descriptor that returns a WebElement or PageComponent
        """
        ac = ActionChains(self.page)
        ac.double_click(element).perform()

    def drag_drop(self, element, target):
        """
        Wrapper of dragging an element to anther using ActionChain

        Args:
            element (WebElement): the element to be dragged
            target (WebElement): the destination element to be dragged to
        """
        ac = ActionChains(self.page)
        ac.drag_and_drop(element, target).perform()


class PageComponent(PageBase):
    """
    The container of a group of related WebElement/PageComponent defined by `PageElement` and its variations. This class inherit `PageBase`.

    How to group elements is up to the user but the practice is to group by functionality. E.g. search box and the button, a label and its input box, etc.
    """
    def __init__(self, element, page):
        super(PageComponent, self).__init__(element, page)


class PageObject(PageBase):
    """
    The page object of a web page. Elements are defined by using `PageElement` or its variations, potentially, they are grouped into `PageComponent`.
    This class inherits `PageBase`. It can be decorated by `decorators.pageconfig` to provide more configurations. See the decorator reference
    for details.
    """

    def __init__(self, drv):
        super(PageObject, self).__init__(drv, self)
        self.cache = PageElementCache(self) if self.enable_cache else None

    def alert(self, timeout=0):
        """
        Wrapper of `WebDriver.switch_to.alert`.
        It can wait for alert to be present before acting on the alert box to prevent unnecessary exceptions.
        If the alert does not show after the waiting period, it returns None which will fail any further action to the alert box.

        Args:
            timeout (int, optional): time to wait before alert presents. Defaults to 0 which means no waiting period.

        Returns:
            The alert box displayed. Return None is timeout.
        """
        page_logger.debug('Switching to alert.')
        try:
            self.wait(EC.alert_is_present(), timeout or self.timeout)
        except TimeoutException:
            return None
        else:
            return self.context.switch_to.alert

    def window(self, window, timeout=0):
        """
        Switch to specified browser window and wait for the window to be loaded.

        Args:
            window (str): window handle saved in `WebDriver.window_handles`. See Selenium ref for details.
            timeout (int, optional): timeout value to wait for the page loading. Defaults to 0.

        Returns:
            The new window to be switched to.
        """
        script = 'return document.readyState == "complete"'
        page_logger.debug('Switching to window[{}].'.format(window))
        if type(window) is int:
            window = self.context.window_handles[window]
        self.context.switch_to.window(window)
        self.wait(lambda driver: driver.execute_script(script), timeout or self.timeout)

    def frame(self, frame):
        """
        Switch to specified frame. A simple wrapper to `WebDriver.switch_to.frame`.

        Args:
            frame (str): frame name.
        """
        page_logger.debug('Switching to Frame[{}]'.format(frame))
        self.context.switch_to.frame(frame)

    def goto(self, next_page, window=None, frame=None, timeout=0):
        """
        Cast the page or a page in window/frame to `PageObject` of the class specified by `next_page`

        Args:
            next_page (str): the class of the next page. It is provided by a string specifying the absolute path to the clas
            window (str, optional): window handler. Defaults to None, must present if go to window or frame.
            frame (str, optional): frame name. Defaults to None, must present if go to frame.
            timeout (int, optional): timeout value for the page to load. Defaults to 0.

        Returns:
            PageObject: a `PageObject` represents the changed page
        """
        if window is not None:
            self.window(window, timeout)
        if frame is not None:
            self.frame(frame)
        return self.changepage(next_page, self.context)

    def resize(self, width=None, height=None):
        """
        Resize the window to the specified width and height. This method is useful when capturing screenshot in headless browser
        Note: it only works in headless Chrome at the moment. The viewport size will be limited to screen resolution if used in GUI mode

        The resize uses Javascript to change viewport width/heigh. Both width and height must be valid Javascript that returns a number.
        The returned number is used as width/height. If width or height is not given, it will use scrollHeight/scrollWidth as width/height
        to provide the maximam viewport without scrolling.

        Args:
            width (str, optional): Javascript to calculate the new viewport width. Defaults to None.
            height (str, optional): Javascript to calculate the new viewport height. Defaults to None.
        """

        height_script = height if height else 'return document.body.parentNode.scrollHeight'
        width_script = width if width else 'return document.body.parentNode.scrollWidth'
        height = self.execute_script(height_script)
        width = self.execute_script(width_script)
        self.set_window_size(width, height)

    def capture_screen(self, fname):
        """
        Resize the window to eliminate any scrolling then capture screenshot.

        Args:
            fname (str): file name to save the screenshot
        """
        self.resize()
        self.save_screenshot(fname)

    @staticmethod
    def changepage(next_page, drv):
        """
        Cast the current page to the specified class.

        Args:
            next_page (str): the class of the next page. It is provided by a string specifying the absolute path to the clas
            drv (WebDriver): the web driver object that drives the browser

        Returns:
            PageObject: new `PageObject` of the specified class
        """
        page_logger.debug('Changing page to <{}>'.format(next_page))
        path, cls = next_page.rsplit('.', 1)
        m = import_module(path)
        cls = getattr(m, cls)
        return cls(drv)


class PageTable(PageComponent):
    """
    `PageTable` is a type of `PageComponent` that behaves as a table. It provides ability to search and allows `[]`
    syntax to access rows in the table.
    Note: It will be slow when the table contains large amount of rows for all rows are fetched and saved in a list. A
    future improvement is to provide a generator version of query.

    `PageTable` needs to be configured with a locator `_row_locator` in raw Selenium locator format to find rows
    It also needs a `PageComponent` which is a subclass of `PageComponent` to convert a row to a proper object.
    An optional setting `_column_locator` can also be provided to fetch a column as array. This needs that all columns
    have the unified locator that can be parameterized with one template. Column cannot be fetched if `_column_locator`
    is not set. All settings can be defined directly in the class as class attributes but in practice they are passed in
    by using `decorators.tableconfig`.

    `__getitem__()` and `__len__()` are overridden in this class. `[]` syntax will return the row indicated by the index
    and `1en()` will return total number of rows in the table.

    `PageTable` can be queryed by using `query()` defined in this class. The method takes keyword arguments as
    conditions to the query. The key are treated as attributes of the row object and the value is the expected criteria
    of the attribute. The value can be a single value which will be used as the expected attribute. It also can be a
    funtion that take the attribute as parameter and returns a boolean. If it returns True, the row will be added to the
    result. If no condition is supplied, it will return all rows in the table.

    Similar to `query()`, another method `apply()` can be used to modify rows filtered out by specific conditions. It
    uses the same set of arguments plus an `action` which is a function taking the matching row as input.
    """

    _row_locator = ('', '')
    _column_locator = ('', '')
    _row_component = PageComponent

    def __getitem__(self, index):
        """Get a row by index from the table"""
        row = self._all_rows()[index]
        return self._row_component(row, self.page) if self._row_component else row

    def __len__(self):
        """Return the total row number"""
        return len(self._all_rows())

    def _all_rows(self):
        """Fetch all rows in the table in a list"""
        if self.page.cache is not None:
            context_id, locator = self.context._id, self._row_locator
            context_hash = self.get_attribute('outerHTML')
            elements = self.page.cache.read(context_id, context_hash, locator)
        else:
            elements = []
        if not elements:
            elements = self.context.find_elements(*self._row_locator)
            if self.page.cache is not None:
                self.page.cache.write(context_id, context_hash, locator, elements)
        return elements

    def _expand_conditions(self, conditions):
        """
        Normalize query conditions. Expand single value condition to lambda.

        Args:
            conditions (dict): conditions used for querying the table

        Returns:
            dict: normalized conditions. All conditions are callables with one parameter and returns bool
        """
        expanded = {}
        for k, v in conditions.items():
            if not callable(v):
                def cond(x, ref=v):
                    t = x.get_attribute('textContent').strip() if isinstance(x, WebElement) else x
                    page_logger.debug('value[{}] == expected[{}]? => {}'.format(t, ref, t == ref))
                    return t == ref
            else:
                def cond(x, c=v):
                    result = c(x)
                    page_logger.debug('value[{}] matching <lambda function>? => {}'.format(x, result))
                    return result
            expanded[k] = cond
            # expanded[k] = lambda x, ref=v: \
            #     (x.get_attribute('textContent') if isinstance(x, WebElement) else x).strip() == ref
        return expanded

    def query(self, once=False, **conditions):
        """
        Query the table by specified conditions.

        Args:
            once (bool, optional): If True, terminate at the first match and return the row. Defaults to False.

        Returns:
            If `once` is False, it will retrun all rows matching specified conditions in a list. `[]` will be returned
            if no rows are found. If `once` is set to True, the row object matching conditions is returned, return None
            if no row matches the condition.
        """
        page_logger.debug('Querying table with conditions: {}...'.format(str(conditions)))
        rows = self._all_rows()
        result = []

        conditions = self._expand_conditions(conditions)

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

    def apply(self, action, once=False, **conditions):
        """
        Similar to query, this method apply an action to matching rows in the table.

        Args:
            action (callable): the action to be applied to the row. It takes a single parameter representing the row object
            once (bool, optional): If True, terminate at the first match. Defaults to False.
        """
        page_logger.debug('Applying operation to table with conditions: {}...'.format(str(conditions)))
        rows = self._all_rows()
        result = []

        conditions = self._expand_conditions(conditions)

        for i, row in enumerate(rows):
            page_logger.debug('Checking row {}...'.format(i))

            if self._row_component:
                row = self._row_component(row, self.page)

            if not conditions or all(cond(getattr(row, attr)) for (attr, cond) in conditions.items()):
                page_logger.debug('Found matching row: {}'.format(i))
                action(row)

            if result and once:
                page_logger.debug('Terminating immediately after found.')
                break

    def column(self, column_ident, component=None):
        """
        Fetch a column of data as array of PageElement.

        It uses the _column_locator and solidify the locator by `column_ident`

        Args:
            column_ident (str or tuple): paramters to solidify the column locator
            component (class): the class that the cell should be cast as

        Returns:
            list: a list of `PageElement` or `PageComponent` found by the column
        """
        if type(column_ident) not in (tuple, list):
            column_ident = (column_ident,)
        locator = self._column_locator[0], self._column_locator[1].format(*column_ident)
        cells = self.context.find_elements(*locator)
        return [component(c, self.page) for c in cells] if component is not None else cells
