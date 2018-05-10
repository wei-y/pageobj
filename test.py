from page_object import PageObject, PageElement, PageComponent, PageTable
from selenium import webdriver
import logging

page_logger = logging.getLogger('PageObject')


class TestLoginPage(PageObject):
    user = PageElement('input[name="email"]', by='css selector')
    password = PageElement('input[name="password"]', by='css selector')
    login_button = PageElement('button[type="submit"]', by='css selector')

    def login(self, user, password):
        self.user = user
        self.password = password
        self.login_button.click()
        return self.goto('test.DashboardPage')


class PageNavigator(PageComponent):
    home = PageElement('DASHBOARD', by='link text')
    frontend = PageElement('Frontend', by='link text')
    configuration = PageElement('Configuration', by='link text')
    settings = PageElement('Settings', by='link text')
    bookings = PageElement('Bookings', by='link text')

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
    tick = PageElement('td:nth-child(1) input[type="checkbox"]', by='css selector')
    number = PageElement('td:nth-child(2)', by='css selector')
    id_ = PageElement('td:nth-child(3)', by='css selector')
    reference = PageElement('td:nth-child(4)', by='css selector')
    customer = PageElement('td:nth-child(5)', by='css selector')
    module = PageElement('td:nth-child(6)', by='css selector')
    date = PageElement('td:nth-child(7)', by='css selector')
    total = PageElement('td:nth-child(8)', by='css selector')
    paid = PageElement('td:nth-child(9)', by='css selector')
    remaining = PageElement('td:nth-child(10)', by='css selector')
    status = PageElement('td:nth-child(11)', by='css selector')
    view_button = PageElement('td:nth-child(12) a:nth-child(1)', by='css selector')
    edit_button = PageElement('td:nth-child(12) a:nth-child(2)', by='css selector')
    delete_button = PageElement('td:nth-child(12) a:nth-child(3)', by='css selector')

    def view(self):
        self.view_button.click()
        self.pageobj.wait_ajax()
        return 'test.BasePage'

    def edit(self):
        self.edit_button.click()
        self.pageobj.wait_ajax()
        return 'test.BasePage'

    def delete(self):
        self.delete_button.click()
        self.pageobj.wait_ajax()
        self.pageobj.alert().accept()


class BookingTable(PageTable):
    __row_locator__ = ('css selector', 'tbody tr')
    __row_component__ = BookingRow


class BookingsPage(BasePage):
    print_button = PageElement('Print', by='link text')
    export_csv = PageElement('Export into CSV', by='link text')
    booking_table = PageElement('#content table', by='css selector', component=BookingTable)


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
    page = page.window(0)
