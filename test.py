from page_object import PageObject, PageElement, PageComponent, PageTable, nextpage, pageconfig
from selenium import webdriver
from selenium.webdriver.common.by import By


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


@pageconfig(default_by=By.LINK_TEXT)
class PageNavigator(PageComponent):
    home = PageElement('DASHBOARD')
    frontend = PageElement('Frontend')
    configuration = PageElement('Configuration')
    settings = PageElement('Settings')
    bookings = PageElement('Bookings')

    @nextpage({
        'frontend': 'test.FrontendPage',
        'bookings': 'test.BookingsPage',
    })
    def nav(self, *menus):
        for m in menus:
            getattr(self, m).click()
            self.page.wait_ajax()
        return menus[-1]


class BasePage(PageObject):
    navigator = PageElement('nav', by='tag name', component=PageNavigator)


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

    @nextpage('test.BasePage')
    def edit(self):
        self.edit_button.click()
        self.page.wait_ajax()

    def delete(self):
        self.delete_button.click()
        self.page.wait_ajax()
        self.page.alert().accept()


@pageconfig(row_locator=(By.CSS_SELECTOR, 'tbody tr'), row_component=BookingRow)
class BookingTable(PageTable):
    pass


@pageconfig(default_by=By.LINK_TEXT)
class BookingsPage(BasePage):
    print_button = PageElement('Print')
    export_csv = PageElement('Export into CSV')
    booking_table = PageElement('#content table', by=By.CSS_SELECTOR, component=BookingTable)


if __name__ == '__main__':
    drv = webdriver.Firefox()
    drv.get('https://www.phptravels.net/admin')
    page = TestLoginPage(drv)
    page = page.login('admin@phptravels.com', 'demoadmin')
    page = page.navigator.nav('bookings')
    page.save_screenshot('test1.png')
    for i in range(5):
        page = page.booking_table[i].view()
        page.save_screenshot('test{}.png'.format(i))
        page.close()
        page = page.goto('test.BookingsPage', window=0)
