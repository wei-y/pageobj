from page_object import PageObject, PageSchema, Locator
from selenium import webdriver
import logging

page_logger = logging.getLogger('PageObject')


class TestHomeSchema(PageSchema):
    sign_in = Locator('Sign in', 'link text')


class TestLoginSchema(PageSchema):
    user = Locator('email')
    password = Locator('passwd')
    login_button = Locator('SubmitLogin')


class TestMainSchema(PageSchema):
    menu = Locator('block-top-menu', wrapper=TestMainMenu)


class TestHomePage(PageObject):
    __schema__ = TestHomeSchema

    def to_login(self):
        self.sign_in.click()
        return self.goto('test.TestLoginPage')


class TestLoginPage(PageObject):
    __schema__ = TestLoginSchema

    def login(self, user, password):
        self.user = user
        self.password = password
        self.login_button.click()
        return self.goto('test.TestMainPage')


class TestMainPage(PageObject):
    __schema__ = TestMainSchema


if __name__ == '__main__':
    drv = webdriver.Firefox()
    drv.get('http://automationpractice.com/')
    page = TestHomePage(drv)
    page = page.to_login()
    page = page.login('yyloginbin@gmail.com', '12345')
