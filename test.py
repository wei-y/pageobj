from page_object import PageObject, PageElement, PageComponent
from selenium import webdriver
import logging

page_logger = logging.getLogger('PageObject')


class TestHomePage(PageObject):
    sign_in = PageElement('Sign in', by='link text')

    def to_login(self):
        self.sign_in.click()
        return self.goto('test.TestLoginPage')


class TestLoginPage(PageObject):
    user = PageElement('email')
    password = PageElement('passwd')
    login_button = PageElement('SubmitLogin')

    def login(self, user, password):
        self.user = user
        self.password = password
        self.login_button.click()
        return self.goto('test.AccountPage')


class AccountMenu(PageComponent):
    order_history = PageElement('Order history and details', by='link text')

    target = {
        'order_history': 'test.HistoryPage'
    }

    def click(self, name):
        menu = getattr(self, name)
        menu.click()
        return self.target[name]


class AccountPage(PageObject):
    account_menu = PageElement('center_column', wrapper=AccountMenu)

    def goto(self, name):
        return self.account_menu.click(name)


class HistoryPage(PageObject):
    pass


if __name__ == '__main__':
    drv = webdriver.Firefox()
    drv.get('http://automationpractice.com/')
    page = TestHomePage(drv)
    page = page.to_login()
    page = page.login('yyloginbin@gmail.com', '12345')
    page = page.goto('order_history')
