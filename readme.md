# Selenium Page Object in Python
## Defining a page
Define a page by inherit from `PageObject` and declare all elements.
A default `By` can be configed by using decorator `pageconfig`.

Elements defined on the page are wrapped Selenium page elements by default. They can be used directly in page actions by using `.` notation. The element will be evaluated at accessing moment.

The next page of the action can be defined by using decorator `nextpage`. the parameter to the decorator is the package/module name of the next page object.
```Python
@pageconfig(default_by=By.CSS_SELECTOR)
class TestLoginPage(PageObject):
    user = PageElement('input[name="email"]')
    password = PageElement('input[name="password"]')
    login_button = PageElement('button[type="submit"]')

    @nextpage('test.BasePage')
    def login(self, user, password):
        self.user = user
        self.password = password
        self.login_button.click()
```

## Page component
A page component can be defined in the similar way as the `PageObject` only it is inherited from `PageComponent`.
The defined component can be used in other pages like the raw page element above.
```Python
@pageconfig(default_by=By.LINK_TEXT)
class PageNavigator(PageComponent):
    home = PageElement('DASHBOARD')
    frontend = PageElement('Frontend')
    configuration = PageElement('Configuration')
    settings = PageElement('Settings')
    bookings = PageElement('Bookings')

    @nextpage('bookings': 'test.BookingsPage')
    def bookings(self):
        for m in menus:
            self.bookings.click()
            self.page.wait_ajax()

class BasePage(PageObject):
    navigator = PageElement('nav', by='tag name', component=PageNavigator)
```

## Defining Table
A table is any table-like structure defined in the DOM. Of course a `<Table>` can be defined in this way. The benefit of using `PageTable` is that it provides index access and query ability.

A table row is defined as a `PageComponent` with each column as a sub-element or component. Since it is a Component, action can be defined in table row as well.
```Python
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

    @nextpage('test.BasePage')
    def view(self):
        windows_count = len(self.page.window_handles)
        self.view_button.click()
        self.page.wait_ajax()
        self.page.wait(lambda drv: len(drv.window_handles) > windows_count)
        self.page.window(-1)
```

Once a table row is defined, it then can be used to define a `PageTable` by specify the row selector and class in `pageconfig` decorator. Then, the defined table can be used as a component in a `PageObject`.
```Python
@pageconfig(row_locator=(By.CSS_SELECTOR, 'tbody tr'), row_component=BookingRow)
class BookingTable(PageTable):
    pass

@pageconfig(default_by=By.LINK_TEXT)
class BookingsPage(BasePage):
    print_button = PageElement('Print')
    export_csv = PageElement('Export into CSV')
    booking_table = PageElement('#content table', by=By.CSS_SELECTOR, component=BookingTable)
```

Table rows can be accessed by using index notation. Table can also be queried by providing filters to columns. The filter can be a string or a function returning Boolean.
```Python
row = page.booking_table[0]
result = page.booking_table.query(paid=False, total=lambda v: v>100)
```

## And that's it!
The full example is in `test.py`
