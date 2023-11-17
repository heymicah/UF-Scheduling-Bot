import asyncio
import json
import traceback
from datetime import datetime
from playwright.async_api import async_playwright


async def main():
    # Get user information
    username, password, sch_time = get_user_info()

    # Launch Browser
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=50)
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
        await asyncio.sleep(15)
        await page_login.locator("button:has-text(\"Yes, this is my device\")").click()
        await asyncio.sleep(5)

        # Open Scheduling Pages
        link = 'https://one.uf.edu/myschedule/2241'
        course_numbers = [[10774, 10718, 25465], [26055]]
        count = []
        for i in range(len(course_numbers)):
            asyncio.create_task(scheduling_tasks(context, link, course_numbers[i], sch_time, count, i))

        while len(count) != len(course_numbers):
            await asyncio.sleep(2)

        await asyncio.sleep(30)
        await browser.close()


async def scheduling_tasks(context, link, course_number, sch_time, count, i):
    try:
        print(f'[Task {i + 1}][{course_number[0]}] Opening Browser')
        page_task = await context.new_page()
        print(f'[Task {i + 1}][{course_number[0]}] Opening Link')
        await page_task.goto(link)

        # Wait for Scheduled Time
        current_time = datetime.now()
        time_remaining = (sch_time - current_time).total_seconds()
        print(f'[Task {i + 1}][{course_number[0]}] Sleeping for {time_remaining} seconds')
        await asyncio.sleep(time_remaining)

        # Continue after sleep
        print(f'[Task {i + 1}][{course_number[0]}] Searching for Class')
        await page_task.goto(f'https://one.uf.edu/soc/registration-search/2241?term="2241"&category="CWSP"&class-num="{course_number[0]}"')

        # Add Class
        try:
            print(f'[Task {i + 1}][{course_number[0]}] Registering for class')

            # Register for class
            success = await add_class(page_task, course_number[0], i)
            if success == False:
                raise Exception
            
        except:
            # Initialize class list that can be waitlisted
            waitlist_classes = []
            try: 
                await page_task.locator("button:has-text(\"+ Add to Wait List\")").wait_for(timeout=1500)
                waitlist_classes.append(course_number[0])
            except:
                pass

            # Backup Tasks
            if len(course_number) > 1:
                print(f'[Task {i + 1}][{course_number[0]}] Class Full: Starting backup tasks')
                backup_task = await context.new_page()
                for course in range(1, len(course_number)):
                    await backup_task.goto(f'https://one.uf.edu/soc/registration-search/2241?term="2241"&category="CWSP"&class-num="{course_number[course]}"')
                    try:
                        await backup_task.locator("button:has-text(\"+ Add Class\")").wait_for(timeout=1500)
                        print(f'[Task {i + 1}][{course_number[course]}] Registering for class')
                        success = await add_class(backup_task, course_number[course], i)
                        if success == True:
                            break
                    except:
                        try: 
                            await page_task.locator("button:has-text(\"+ Add to Wait List\")").wait_for(timeout=1500)
                            waitlist_classes.append(course_number[course])
                        except:
                            pass

        # Waitlist Classes
        if len(waitlist_classes) > 0:
            print('Adding user to waitlists')
            for wl_course in waitlist_classes:
                await page_task.goto(f'https://one.uf.edu/soc/registration-search/2241?term="2241"&category="CWSP"&class-num="{wl_course}"')
                await add_waitlist(page_task, wl_course, i, link)

        # Return count
        count.append(1)

    except:
        print(f'[Task {i + 1}][{course_number}] Fatal Error')
        count.append(0)

async def add_class(page_task, course_number, i):
    try:
        await page_task.locator("button:has-text(\"+ Add Class\")").wait_for(timeout=1500)
        await page_task.locator("button:has-text(\"+ Add Class\")").click()
        await page_task.get_by_role("button", name='Add').click()
        print(f'[Task {i + 1}][{course_number}] Processing')
        await asyncio.sleep(7)
        success_message = 'The following class was ADDED  successfully'
        if await page_task.get_by_text('The following class').text_content() == success_message:
            print(f'[Task {i + 1}][{course_number}] Successfully Added Class')
            return True
        else:
            print(f'[Task {i + 1}][{course_number}] Failed: Could not add class')
            return False
    except:
        print(f'[Task {i + 1}][{course_number}] Class Full / Fatal Error')
        return False
    

async def add_waitlist(page_task, course_number, i, link):
    print(f'[Task {i + 1}][{course_number}] Class Full: Registering for Waitlist')
    await page_task.locator("button:has-text(\"+ Add to Wait List\")").click()
    await page_task.get_by_role("button", name='Add to Wait List').click()
    print(f'[Task {i + 1}][{course_number}] Processing')
    await asyncio.sleep(7)
    success_message = 'The following class was ADDED  to the wait list  successfully'
    if await page_task.get_by_text('The following class').text_content() == success_message:
        print(f'[Task {i + 1}][{course_number}] Successfully Added to Waitlist')
        await page_task.goto(link)
        position = (await page_task.get_by_text('Wait List position').text_content())[-1]
        print(f'[Task {i + 1}][{course_number}] Wait list position: {position}')
    else:
        print(f'[Task {i + 1}][{course_number}] Failed: Could not add to waitlist')


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