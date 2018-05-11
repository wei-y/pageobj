from page_object import PageObject, PageElement, PageComponent, PageTable
from selenium import webdriver
from selenium.webdriver.common.by import By


class TestLoginPage(PageObject):
    __default_by__ = By.CSS_SELECTOR

    user = PageElement('input[name="email"]')
    password = PageElement('input[name="password"]')
    login_button = PageElement('button[type="submit"]')

    def login(self, user, password):
        self.user = user
        self.password = password
        self.login_button.click()
        return self.goto('test.DashboardPage')


class PageNavigator(PageComponent):
    __default_by__ = By.LINK_TEXT

    home = PageElement('DASHBOARD')
    frontend = PageElement('Frontend')
    configuration = PageElement('Configuration')
    settings = PageElement('Settings')
    bookings = PageElement('Bookings')

    _links = {
        'bookings': 'test.BookingsPage'
    }


class BasePage(PageObject):
    navigator = PageElement('nav', by='tag name', component=PageNavigator)

    def nav_to(self, *menus):
        for m in menus:
            getattr(self.navigator, m).click()
            self.wait_ajax()
        return self.goto(self.navigator._links[menus[-1]])


class DashboardPage(BasePage):
    pass


class BookingRow(PageComponent):
    __default_by__ = By.CSS_SELECTOR

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

    def view(self):
        self.view_button.click()
        self.b.wait_ajax()
        return 'test.BasePage'

    def edit(self):
        self.edit_button.click()
        self.b.wait_ajax()
        return 'test.BasePage'

    def delete(self):
        self.delete_button.click()
        self.b.wait_ajax()
        self.b.alert().accept()


class BookingTable(PageTable):
    __row_locator__ = ('css selector', 'tbody tr')
    __row_component__ = BookingRow


class BookingsPage(BasePage):
    __default_by__ = By.LINK_TEXT

    print_button = PageElement('Print')
    export_csv = PageElement('Export into CSV')
    booking_table = PageElement('#content table', by=By.CSS_SELECTOR, component=BookingTable)


if __name__ == '__main__':
    drv = webdriver.Firefox()
    drv.get('https://www.phptravels.net/admin')
    page = TestLoginPage(drv)
    page = page.login('admin@phptravels.com', 'demoadmin')
    page = page.nav_to('bookings')
    page.save_screenshot('test1.png')
    page.booking_table[0].view()
    page.window(-1).save_screenshot('test2.png')
    page.window(-1).close()
    page.window(0)
