import asyncio
import json
import requests
from datetime import datetime
from playwright.async_api import async_playwright

async def main():
    # Get user information
    username, password, sch_time, webhook = get_user_info()

    # Launch Browser
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=100)
        context = await browser.new_context()
        page_login = await context.new_page()
        await page_login.goto("http://one.uf.edu")
        async with page_login.expect_navigation():
            await page_login.locator("button:has-text(\"Log in with GatorLink\")").click()

        # Username and Password Fill
        print(f'[{str(datetime.now().time())}] Logging in ...')
        await page_login.fill("input#username", username)
        await page_login.fill("input#password", password)
        async with page_login.expect_navigation():
            await page_login.locator("button:has-text(\"Login\")").click()
        print(f'[{str(datetime.now().time())}] Waiting for 2FA ...')

        # Wait for login
        await asyncio.sleep(15)
        await page_login.locator("button:has-text(\"Yes, this is my device\")").click()
        print(f'[{str(datetime.now().time())}] Logged in')
        await asyncio.sleep(5)

        # Open Scheduling Pages
        link = 'https://one.uf.edu/myschedule/2251'
        course_numbers = [[20886], [23406], [19232], [13387]]
        count = []
        for i in range(len(course_numbers)):
            asyncio.create_task(scheduling_tasks(context, link, course_numbers[i], sch_time, count, i, webhook))

        while len(count) != len(course_numbers):
            await asyncio.sleep(2)

        await asyncio.sleep(30)
        await browser.close()


async def scheduling_tasks(context, link, course_number, sch_time, count, i, webhook):
    # Set timeout time
    global timeout_time
    timeout_time = 3000     # Wait for page to load

    try:
        print(f'[{str(datetime.now().time())}][Task {i + 1}][{course_number[0]}] Opening Browser')
        page_task = await context.new_page()
        print(f'[{str(datetime.now().time())}][Task {i + 1}][{course_number[0]}] Opening Link')
        await page_task.goto(link)

        # Wait for Scheduled Time
        current_time = datetime.now()
        time_remaining = (sch_time - current_time).total_seconds()
        print(f'[{str(datetime.now().time())}][Task {i + 1}][{course_number[0]}] Sleeping for {time_remaining} seconds')
        await asyncio.sleep(time_remaining)

        # Continue after sleep
        print(f'[{str(datetime.now().time())}][Task {i + 1}][{course_number[0]}] Searching for Class')
        await page_task.goto(f'https://one.uf.edu/soc/registration-search/2251?term="2251"&category="CWSP"&class-num="{course_number[0]}"')

        # Add Class
        try:
            print(f'[{str(datetime.now().time())}][Task {i + 1}][{course_number[0]}] Registering for class')

            # Register for class
            success = await add_class(page_task, course_number[0], i, webhook)
            if success == False:
                raise Exception

        except:
            # Initialize waitlist list
            waitlist_classes = []

            # Backup Tasks
            if len(course_number) > 1:
                print(f'[{str(datetime.now().time())}][Task {i + 1}][{course_number[0]}] Class Full: Starting backup tasks')
                backup_task = await context.new_page()
                for course in range(1, len(course_number)):
                    await backup_task.goto(f'https://one.uf.edu/soc/registration-search/2251?term="2251"&category="CWSP"&class-num="{course_number[course]}"')
                    try:
                        await backup_task.locator("button:has-text(\"+ Add Class\")").wait_for(timeout=timeout_time)
                        print(f'[{str(datetime.now().time())}][Task {i + 1}][{course_number[course]}] Registering for class')
                        success = await add_class(backup_task, course_number[course], i, webhook)
                        if success == True:
                            break
                    except:
                        try: 
                            await page_task.locator("button:has-text(\"+ Add to Wait List\")").wait_for(timeout=timeout_time)
                            waitlist_classes.append(course_number[course])
                        except:
                            pass

            # Add original class to waitlist
            try:
                await page_task.locator("button:has-text(\"+ Add to Wait List\")").wait_for(timeout=timeout_time)
                waitlist_classes.insert(0, course_number[0])
            except:
                pass

        # Waitlist Classes
        if len(waitlist_classes) > 0:
            print(f'[{str(datetime.now().time())}] Adding user to waitlists')
            for wl_course in waitlist_classes:
                await page_task.goto(f'https://one.uf.edu/soc/registration-search/2251?term="2251"&category="CWSP"&class-num="{wl_course}"')
                await add_waitlist(page_task, wl_course, i, link, webhook)

        # Return count
        count.append(1)

    except:
        print(f'[{str(datetime.now().time())}][Task {i + 1}][{course_number}] Fatal Error')
        count.append(0)


async def add_class(page_task, course_number, i, webhook):
    try:
        await page_task.locator("button:has-text(\"+ Add Class\")").wait_for(timeout=timeout_time)
        await page_task.locator("button:has-text(\"+ Add Class\")").click()
        await page_task.get_by_role("button", name='Add').click()
        print(f'[{str(datetime.now().time())}][Task {i + 1}][{course_number}] Processing')
        await asyncio.sleep(10)
        success_message = 'The following class was ADDED  successfully'
        if await page_task.get_by_text('The following class').text_content() == success_message:
            success = True
            text = f'[{str(datetime.now().time())}][Task {i + 1}][{course_number}] Successfully Added Class'
            print(text)
            discord_message(text, success, webhook)
            return True
        else:
            success = False
            text = f'[{str(datetime.now().time())}][Task {i + 1}][{course_number}] Failed: Could not add class'
            print(text)
            discord_message(text, success, webhook)
            return False
    except:
        success = False
        text = f'[{str(datetime.now().time())}][Task {i + 1}][{course_number}] Class Full / Fatal Error'
        print(text)
        discord_message(text, success, webhook)
        return False
    

async def add_waitlist(page_task, course_number, i, link, webhook):
    try:
        print(f'[{str(datetime.now().time())}][Task {i + 1}][{course_number}] Class Full: Registering for Waitlist')
        await page_task.locator("button:has-text(\"+ Add to Wait List\")").click()
        await page_task.get_by_role("button", name='Add to Wait List').click()
        print(f'[{str(datetime.now().time())}][Task {i + 1}][{course_number}] Processing')
        await asyncio.sleep(10)
        success_message = 'The following class was ADDED  to the wait list  successfully'
        if await page_task.get_by_text('The following class').text_content() == success_message:
            success = True
            text = f'[{str(datetime.now().time())}][Task {i + 1}][{course_number}] Successfully Added to Waitlist'
            print(text)
            discord_message(text, success, webhook)
            await page_task.goto(link)
            position = (await page_task.get_by_text('Wait List position').text_content())[-1]
            print(f'[{str(datetime.now().time())}][Task {i + 1}][{course_number}] Wait list position: {position}')
        else:
            success = False
            text = f'[{str(datetime.now().time())}][Task {i + 1}][{course_number}] Failed: Could not add to waitlist'
            print(text)
            discord_message(text, success, webhook)
    except:
        success = False
        text = f'[{str(datetime.now().time())}][Task {i + 1}][{course_number}] Failed: Fatal Error'
        print(text)
        discord_message(text, success, webhook)


def get_user_info():
    try:
        with open('userdata.txt') as f:
            data = f.read()
            user_data = json.loads(data)
            username = user_data["Username"]
            password = user_data["Password"]
            webhook = user_data["Webhook"]

    except IOError:
        data = {}
        data["Username"] = input("UF Username: ")
        data["Password"] = input("Password: ")
        while True:
            try:
                data["Webhook"] = input("Discord Webhook: ")
                test_message = {
                    "embeds": [{
                    "title": "Test",
                    "description": "Test Message"
                    }]
                }
                x = requests.post(data["Webhook"], json=test_message)
                if x.status_code == 204:
                    break
                else:
                    raise Exception
            except:
                print("Invalid Webhook")
        with open('userdata.txt', 'w') as f:
            f.write(json.dumps(data))
        username = data["Username"]
        password = data["Password"]
        webhook = data["Webhook"]

    sch_time = datetime.strptime(input("Scheduling Time (Ex: 10/24/23 14:00:00): "), '%m/%d/%y %H:%M:%S')
    return username, password, sch_time, webhook


def discord_message(text, bool, webhook):

    if bool == True:
        title = "Success"
        color = 65280
    else:
        title = "Failed"
        color = 16711680

    message = {
        "embeds": [{
        "title": f"{title}",
        "color": color,
        "description": f"{text}"
        }]
    }
    
    x = requests.post(webhook, json=message)

if __name__ == '__main__':
    asyncio.run(main())