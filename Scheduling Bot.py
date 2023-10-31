import asyncio
import json
from datetime import datetime
from playwright.async_api import async_playwright

async def main():

    # Get user information
    username, password, sch_time = get_user_info()

    # Launch Browser
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless = False, slow_mo=50)
        context = await browser.new_context()
        page_login = await context.new_page()
        await page_login.goto("http://one.uf.edu")
        async with page_login.expect_navigation():
            await page_login.locator("button:has-text(\"Log in with GatorLink\")").click()
        
        # Username and Password Fill
        await page_login.fill("input#username", username)
        await page_login.fill("input#password", password)
        async with page_login.expect_navigation():
            await page_login.locator("button:has-text(\"Login\")").click()
        
        # Wait for login
        await asyncio.sleep(10)

        # Open Scheduling Pages
        link = 'https://one.uf.edu/myschedule/2241'
        course_numbers = [15755, 15713]
        for i in range(len(course_numbers)):
            asyncio.create_task(scheduling_tasks(context, link, course_numbers[i], sch_time))
        
        await asyncio.sleep(30)

        await browser.close()


async def scheduling_tasks(context, link, course_number, sch_time):
    page_task = await context.new_page()
    await page_task.goto(link)
    
    # Wait for Scheduled Time
    current_time = datetime.now()
    time_remaining = (sch_time - current_time).total_seconds()
    await asyncio.sleep(time_remaining)
    await page_task.goto(f'https://one.uf.edu/soc/registration-search/{link[-4:]}')

    # Input Class Number
    await page_task.fill("input#class-number", str(course_number))
    async with page_task.expect_navigation():
        await page_task.locator("button:has-text(\"Search\")").click()
    
    # Add Class
    await page_task.locator("button:has-text(\"+ Add Class\")").click()
    await page_task.get_by_role("button", name='Add').click()

def get_user_info():
    try:
        with open('userdata.txt') as f: 
            data = f.read()
            user_data = json.loads(data)
            username = user_data["Username"]
            password = user_data["Password"]

    except IOError:
        data = {}
        data["Username"] = input("UF Username: ")
        data["Password"] = input("Password: ")
        with open('userdata.txt', 'w') as f: 
            f.write(json.dumps(data))
        username = data["Username"]
        password = data["Password"]
    
    sch_time = datetime.strptime(input("Scheduling Time (Ex: 10/24/23 14:00:00): "), '%m/%d/%y %H:%M:%S')
    return username, password, sch_time

if __name__ == '__main__':
    asyncio.run(main())