# Selenium Page Object in Python

This document is using the admin module of [PHPTravel Demo](https://phptravels.com/demo/) site to illustrate the usage of this package.

## Defining a page

The Admin login page can be defined as following.
```python
@pageconfig(default_by=By.CSS_SELECTOR)
class TestLoginPage(PageObject):
    user = PageElement('input[name="email"]')
    password = PageElement('input[name="password"]')
    login_button = PageElement('button[type="submit"]')

    @nextpage('test.BasePage')
    def login(self, user, password):
        self.user = user
        self.password = password
        with self.wait_page_loaded_after(timeout=10):
            self.login_button.click()
```

### PageObject

A page is defined by creating a class inherited from `PageObject` and declare
all interested elements in the class as class attributes. An element declaration is an instance of `PageElement` class with selector as parameter.
When accessing the element, it will return a raw Selenium WebElement, a
`PageComonent` or the text/value of the element based on parameters to the
`PageElement` initiator.

### Adding actions

Page actions are defined as normal class methods which will us elements
declared previously. Elements can be get by using `.` notation on `self` and
will be evaluated at runtime. Elements can also be set by using assign
statement. Acceptable type of Values is based on the type of the element.

If the action is leading to another page which is also defined as a
`PageObject`, a decorator `nextpage()` can be used on the action to describe
the package/module path string to the page class.

### Default page settings

Using decorator `pageconfig()` to the `PageObject` to define the default `By`
of element selectors and default timeout when accessing `PageElement`

## PageComponent

The base Dashborad page can be defined as following. Notice that the navigator
is defined as a `PageComponent`.
```python
@pageconfig(default_by=By.LINK_TEXT)
class PageNavigator(PageComponent):
    bookings = PageElement('Bookings')

    @nextpage({
        'bookings': 'test.test.BookingsPage',
    })
    def nav(self, menu):
        with WaitAJAXAfter(self.page):
            getattr(self, menu).click()
        return menu

@pageconfig(default_by=By.TAG_NAME)
class BasePage(PageObject):
    navigator = PageElement('aside', component=PageNavigator)
```

After logging in, the dashboard is more complex. Here a class containing
only the navigator is defined as the base of each different pages. The
navigator is a relatively independent section thus it is defined as a component
using `PageComponent`.

A `PageComponent` is similar to `PageObject`. It contains sub-elements the same
way as `PageObject`. The difference is that all sub-element is defined in the
context of the container component.

A `PageComponent` can be used in other `PageObject` or nest in other `PageComponent` by passing in the component parameter to `PageElement`
definition.

Decorators applicable to `PageObject` are also applicable to `PageComponent`.

## PageTable

The Booking page can be defined as following. Notice that the main table is
defined as a `PageTable`.
```python
@pageconfig(default_by=By.CSS_SELECTOR)
class BookingRow(PageComponent):
    tick = PageElement('td:nth-child(1) input[type="checkbox"]')
    number = PageElement('td:nth-child(2)')
    id_ = PageElement('td:nth-child(3)')
    reference = PageElement('td:nth-child(4)')
    customer = PageElement('td:nth-child(5)')
    module = PageElement('td:nth-child(6)')
    date = PageElement('td:nth-child(7)')
    total = PageElement('td:nth-child(8)')
    paid = PageElement('td:nth-child(9)')
    remaining = PageElement('td:nth-child(10)')
    status = PageElement('td:nth-child(11)')
    view_button = PageElement('td:nth-child(12) a:nth-child(1)')
    edit_button = PageElement('td:nth-child(12) a:nth-child(2)')
    delete_button = PageElement('td:nth-child(12) a:nth-child(3)')

    @nextpage('test.test.BasePage')
    def view(self):
        windows_count = len(self.page.window_handles)
        with WaitAJAXAfter(self.page):
            self.view_button.click()
        self.page.wait(lambda drv: len(drv.window_handles) > windows_count)
        self.page.window(-1)

    @nextpage('test.test.BasePage')
    def edit(self):
        with WaitAJAXAfter(self.page):
            self.edit_button.click()

    def delete(self):
        with WaitAJAXAfter(self.page):
            self.delete_button.click()
        self.page.alert().accept()

@tableconfig(
    row_locator=(By.CSS_SELECTOR, 'tbody tr'),
    row_component=BookingRow
)
class BookingTable(PageTable):
    pass

@pageconfig(default_by=By.LINK_TEXT)
class BookingsPage(BasePage):
    print_button = PageElement('Print')
    export_csv = PageElement('Export into CSV')
    booking_table = PageElement('#content table', by=By.CSS_SELECTOR, component=BookingTable)
```

### Defining a PageTable

A `PageTable` is any table-like structure defined in the DOM. a `<Table>`
could naturally be defined as a `PageTable` but any structure in a table-like
way can do. The benefit of using `PageTable` is that it provides index access
and query ability.

A table row is defined as a `PageComponent` with each column as a sub-element or component. Since it is a Component, action can be defined in table row as well.

Once a table row is defined, it then can be used to define a `PageTable` by specify the row selector and class in `tableconfig` decorator. Then, the defined table can be used as a component in a `PageObject`.

### Accessing by index and querying

Table rows can be accessed by using index notation. Table can also be queried by providing filters to columns. The filter can be a string or a function returning Boolean.

```python
row = page.booking_table[0]
result = page.booking_table.query(paid=False, total=lambda v: v>100)
```

## Waiting

In both `PageObject` and `PageComponent` it can wait for things to happen.
There are two kinds of waitings: a direct waiting and waiting after operation.

A direct waiting can be invoked by calling the `wait()` with a callable as
parameter. The callable is the same as the parameter to `WebDriverWait().until()`.
```python
self.wait(expected_conditions.visibility_of_element_located((By.ID, 'user')))
```

Waiting after operation is called by using the `with` protocal.
```python
with self.wait_page_loaded_after(timeout=10):
    self.login_button.click()
```

## And that's it

The full example is in `test.py`. To run the test file, use the following command.
```shell
python -m unittest discover
```
