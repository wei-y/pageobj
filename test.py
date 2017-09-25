from page_object import PageObject, PageScheme, Locator
from selenium import webdriver
from selenium.webdriver.common.by import By


class GoogleScheme(PageScheme):
    search_box = Locator('lst-ib')
    search_button = Locator(by=By.CSS_SELECTOR, locator='input[name="btnK"]')


class GooglePage(PageObject):
    __scheme__ = GoogleScheme

    def search(self, text):
        self.search_box = text
        self.search_button.click()
        return self.goto('test.GoogleResult')


class GoogleResult(PageObject):

    # __scheme__ = GoogleResultScheme
    # other methods for manipulating data on the result page
    pass


drv = webdriver.Firefox()
drv.get('https://www.google.com')
page = GooglePage(drv)
page = page.search('page object')
page.quit()
print 'Hello Selenium...'
