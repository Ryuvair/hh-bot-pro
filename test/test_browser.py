from core.browser import launch_browser

with launch_browser() as page:
    page.goto("https://hh.ru")
    print("✅ Браузер открыл HH:", page.title())