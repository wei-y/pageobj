from pageobj import PageObject, PageElement, PageComponent, PageTable, WaitPageLoaded
from pageobj.decorators import nextpage, pageconfig, tableconfig
from selenium import webdriver
from selenium.webdriver.common.by import By
from unittest import TestCase


@pageconfig(default_by=By.CSS_SELECTOR)
class TestLoginPage(PageObject):
    user = PageElement('input[name="email"]')
    password = PageElement('input[name="password"]')
    login_button = PageElement('button[type="submit"]')

    @nextpage('test.test.BasePage')
    def login(self, user, password):
        self.user = user
        self.password = password
        with WaitPageLoaded(self):
            self.login_button.click()


@pageconfig(default_by=By.LINK_TEXT)
class PageNavigator(PageComponent):
    bookings = PageElement('Bookings')

    @nextpage({
        'bookings': 'test.test.BookingsPage',
    })
    def nav(self, menu):
        getattr(self, menu).click()
        self.page.wait_ajax()
        return menu


@pageconfig(default_by=By.TAG_NAME)
class BasePage(PageObject):
    navigator = PageElement('aside', component=PageNavigator)


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
        self.view_button.click()
        self.page.wait_ajax()
        self.page.wait(lambda drv: len(drv.window_handles) > windows_count)
        self.page.window(-1)

    @nextpage('test.test.BasePage')
    def edit(self):
        self.edit_button.click()
        self.page.wait_ajax()

    def delete(self):
        self.delete_button.click()
        self.page.wait_ajax()
        self.page.alert().accept()


@tableconfig(row_locator=(By.CSS_SELECTOR, 'tbody tr'), row_component=BookingRow)
class BookingTable(PageTable):
    pass


@pageconfig(default_by=By.LINK_TEXT)
class BookingsPage(BasePage):
    print_button = PageElement('Print')
    export_csv = PageElement('Export into CSV')
    booking_table = PageElement('#content table', by=By.CSS_SELECTOR, component=BookingTable)


class DemoTest(TestCase):

    def setUp(self):
        self.baseurl = 'https://www.phptravels.net/admin'
        self.user = 'admin@phptravels.com'
        self.pwd = 'demoadmin'
        drv = webdriver.Firefox()
        drv.get(self.baseurl)
        self.page = TestLoginPage(drv)

    def tearDown(self):
        self.page.quit()

    def _login(self, usr=None, pwd=None):
        if usr is None:
            usr = self.user
        if pwd is None:
            pwd = self.pwd
        self.page = self.page.login(usr, pwd)

    def test_login(self):
        self._login()
        self.assertEqual(self.page.title, 'Dashboard')

    def test_view_invoice(self):
        self._login()
        self.page = self.page.navigator.nav('bookings')
        for i in range(5):
            self.page = self.page.booking_table[i].view()
            self.page.save_screenshot('test{}.png'.format(i))
            self.page.close()
            self.page = self.page.goto('test.test.BookingsPage', window=0)
