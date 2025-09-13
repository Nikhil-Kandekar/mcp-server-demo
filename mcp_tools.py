import os
import tempfile
import asyncio
import logging
from typing import Literal
from datetime import datetime
import psutil
import nest_asyncio
import playwright.async_api as pw
from mcp.server.fastmcp import FastMCP

nest_asyncio.apply()
logging.basicConfig(level=logging.INFO) 
logger = logging.getLogger(__name__)

class PlayWrightManager:
    """Context manager for Playwright browser sessions.
    A singleton class to manage single Playwright browser to be shared across multiple tools."""

    _instance = None

    def __new__(cls,*args, **kwargs):
        if cls._instance is None:
            cls._instance = super(PlayWrightManager, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance
    def __init__(self, browser_type: Literal["chromium", "firefox", "webkit"] = "chromium", headless: bool = False,
                 viewport: dict = {"width": 1920, "height": 1080}):
        if not self.initialized:
            self.browser_type = browser_type
            self.headless = headless
            self.viewport = viewport
            self.initialized = True
        self.playwright = None
        self.browser = None
        self.context = None
    
    async def ensure_browser(self):
        """Ensure that the browser is started. Returns active page"""
        if not self.playwright:
            self.playwright = await pw.async_playwright().start()
        
        if not self.browser:
            logger.info("Launching browser {self.browser_type} headless={self.headless}")
            browser_factory = getattr(self.playwright, self.browser_type)
            self.browser = await browser_factory.launch(headless=self.headless)
            self.context = await self.browser.new_context(
                viewport=self.viewport
            )
            logger.info("Browser launched")
            self.page = await self.context.new_page()
        
        if not self.context:
            logger.info("Creating new browser context")
            self.context = await self.browser.new_context()
        
        if not self.page:
            logger.info("Creating new page")
            self.page = await self.context.new_page()

        return self.page
    
    async def close(self):
        """Close the browser and cleanup resources."""
        logger.info("Closing browser and cleaning up resources")
        if self.context:
            await self.context.close()
            self.context = None
        if self.browser:
            await self.browser.close()
            self.browser = None
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
        if self.page:
            await self.page.close()
            self.page = None


mcp = FastMCP(
    name ="PlayWrightTools",
    dependencies = ['playwright','nest-asyncio','psutil']
)

pw_manager = PlayWrightManager()
work_dir = os.path.dirname(__file__)


@mcp.tool()
async def browser_navigate(url: str) -> str:
    """
    Navigate to a URL in the browser.

    Args:
        url: The URL to navigate to

    Returns:
        Confirmation message
    """
    if not url or not isinstance(url, str):
        return 'Error: URL must be a non-empty string'

    # Ensure pw_manager instance exists
    global pw_manager
    if pw_manager is None:
        pw_manager = PlayWrightManager(browser_type='chromium', headless=False)

    page = await pw_manager.ensure_browser()
    logger.info(f'Navigating to {url}')

    try:
        await page.goto(url, wait_until='domcontentloaded')
        await page.wait_for_load_state('load', timeout=5000)
    except Exception as e:
        logger.warning(f'Page load timeout or error: {str(e)}')
        return f'Error navigating to {url}: {str(e)}'

    return f"Navigated to {url}"

@mcp.tool(
    name='Browser-Close',
    description="Close the browser and cleanup resources"
)
async def browser_close() -> str:
    """Close the browser and cleanup resources."""
    global pw_manager
    if pw_manager is None:
        return "Browser is not running."
    
    await pw_manager.close()
    pw_manager = None
    return "Browser closed and resources cleaned up."

@mcp.tool(
    name='Kill-all-Chromium-Processes',
    description="Kill all Chromium browser processes to free up system resources"
)
async def kill_all_chrome_instances() -> str:
    """
    Kill all Chrome instances generated via Playwright.

    Returns:
        A confirmation message or an error message.
    """
    logger.info('Attempting to kill all Chrome instances generated via Playwright.')

    try:
        # Iterate through all running processes
        for process in psutil.process_iter(attrs=['pid', 'name', 'exe']):
            try:
                # Check if the process name matches Chrome and its executable path contains "playwright"
                if (
                    process.info['name']
                    and 'chrome' in process.info['name'].lower()
                    and process.info['exe']
                    and 'playwright' in process.info['exe'].lower()
                ):
                    logger.info(
                        f'Terminating process: {process.info["name"]}'
                        f'(PID: {process.info["pid"]}, Path: {process.info["exe"]})'
                    )
                    process.terminate()  # Terminate the process
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                logger.warning(f'Could not terminate process: {str(e)}')

        return 'All Chrome instances generated via Playwright have been terminated.'

    except Exception as e:
        error_msg = f'Failed to kill Chrome instances: {str(e)}'
        logger.error(error_msg)
        return error_msg
    
@mcp.tool(
    name='Browser-Fill',
    description='Fill a form field with text.'
)
async def browser_fill(selector: str, text: str) -> str:
    """
    Fill a form field with text.

    Args:
        selector: CSS or XPath selector to find the form field
        text: Text to fill the form field with

    Returns:
        Fill confirmation
    """
    if not selector or not isinstance(selector, str):
        return 'Error: Selector must be a non-empty string'
    if not isinstance(text, str):
        return 'Error: Text must be a string'

    page = await pw_manager.ensure_browser()
    logger.info(f'Filling text in selector: {selector}')

    try:
        await page.fill(selector, text)
    except Exception as e:
        error_msg = f'Could not fill element: {str(e)}'
        logger.error(error_msg)
        return error_msg

    return f"Filled text in element with selector '{selector}'"

@mcp.tool(
    name='Browser-Find-By-XPath',
    description='Find elements using an XPath expression and return their count.'
)
async def browser_find_by_xpath(xpath: str) -> str:
    """
    Find elements using an XPath expression and return their count.

    Args:
        xpath: XPath expression to find elements

    Returns:
        Count of matching elements
    """
    if not xpath or not isinstance(xpath, str):
        return 'Error: XPath must be a non-empty string'

    # Ensure xpath is formatted properly
    if not xpath.startswith('//') and not xpath.startswith('xpath='):
        xpath = f'xpath={xpath}'

    page = await pw_manager.ensure_browser()
    logger.info(f'Finding elements with XPath: {xpath}')

    try:
        count = len(await page.query_selector_all(xpath))
        return f"Found {count} elements matching XPath '{xpath}'"
    except Exception as e:
        error_msg = f'Error finding elements: {str(e)}'
        logger.error(error_msg)
        return error_msg
    
@mcp.tool(
    name='Browser-Go-Back',
    description='Go back to the previous page in the browser.'
)
async def browser_go_back() -> str:
    """
    Go back to the previous page in the browser.

    Returns:
        Navigation result
    """
    page = await pw_manager.ensure_browser()
    logger.info('Navigating back')

    await page.go_back()

    return 'Navigated back'

@mcp.tool(
    name='Browser-Reload',
    description='Reload the current page.'
)
async def browser_reload() -> str:
    """
    Reload the current page.

    Returns:
        Reload confirmation
    """
    page = await pw_manager.ensure_browser()
    logger.info('Reloading page')

    await page.reload()

    return 'Page reloaded'

@mcp.tool(
    name='Browser-Click',
    description='Click on an element matching the selector'
)
async def browser_click(selector: str) -> str:
    """
    Click on an element matching the selector.

    Args:
        selector: CSS or XPath selector to find the element

    Returns:
        Click confirmation
    """
    if not selector or not isinstance(selector, str):
        return 'Error: Selector must be a non-empty string'

    page = await pw_manager.ensure_browser()
    logger.info(f'Clicking element with selector: {selector}')

    try:
        await page.click(selector, timeout=5000)
    except Exception as e:
        error_msg = f'Could not click element: {str(e)}'
        logger.error(error_msg)
        return error_msg

    return f"Clicked element with selector '{selector}'"

@mcp.tool(
    name='Browser-Save-As-PDF',
    description='Save the current page as a PDF.'
)
async def browser_save_as_pdf(landscape: bool = False, format: str = None) -> str:
    """
    Save the current page as a PDF.

    Args:
        landscape: Whether to save in landscape orientation
        format: Paper format (e.g., 'A4', 'letter') or null for default

    Returns:
        Path to saved PDF file
    """
    if pw_manager.browser_type != 'chromium' or not pw_manager.headless:
        await pw_manager.close()

    pw_manager.browser_type = 'chromium'
    pw_manager.headless = False

    page = await pw_manager.ensure_browser()
    logger.info('Generating PDF')

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    file_name = os.path.join(
        tempfile.gettempdir(),
        f'page_{timestamp}.pdf'
    )
    pdf_options = {}
    if landscape:
        pdf_options['landscape'] = True
    if format:
        pdf_options['format'] = format

    try:
        await page.pdf(path=file_name, **pdf_options)
    except Exception as e:
        error_msg = f'Failed to generate PDF: {str(e)}'
        logger.error(error_msg)
        return error_msg

    return f'PDF saved to {file_name}'

@mcp.tool(
    name='Browser-Screenshot',
    description='Take a screenshot of the current page or a specific element.'
)
async def browser_screenshot(selector: str = None, file_path: str = None) -> str:
    """
    Take a screenshot of the current page or a specific element.

    Args:
        selector: Optional CSS or XPath selector to capture a specific element
        file_path: Optional path to save the screenshot

    Returns:
        Path to saved screenshot
    """
    page = await pw_manager.ensure_browser()
    logger.info('Taking screenshot')

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    file_name = os.path.join(
        tempfile.gettempdir(),
        f'screenshot_{timestamp}.png'
    )

    try:
        if selector:
            logger.info(f'Taking screenshot of element: {selector}')
            element = await page.query_selector(selector)
            if not element:
                return f"Error: Could not find element with selector '{selector}'"
            await element.screenshot(path=file_name)
        else:
            await page.screenshot(path=file_name)
    except Exception as e:
        error_msg = f'Failed to take screenshot: {str(e)}'
        logger.error(error_msg)
        return error_msg

    return f"Screenshot saved to {file_name}"

@mcp.tool(
    name='Browser-Scroll-To-Top',
    description='Scroll the page to the very top.'
)
async def browser_scroll_to_top() -> str:
    """
    Scroll the page to the very top.

    Returns:
        Scroll confirmation
    """
    page = await pw_manager.ensure_browser()
    logger.info('Scrolling to top of page')

    try:
        # Use smooth scrolling for better user experience
        await page.evaluate("""() => {
            window.scrollTo({
                top: 0,
                left: 0,
                behavior: 'smooth'
            });
        }""")

        # Small wait to allow smooth scrolling to complete
        await asyncio.sleep(0.5)
        return 'Scrolled to top of page'
    except Exception as e:
        error_msg = f'Failed to scroll to top: {str(e)}'
        logger.error(error_msg)
        return error_msg
    
@mcp.tool(
    name='Browser-Scroll-To-Bottom',
    description='Scroll the page to the very bottom.'
)
async def browser_scroll_to_bottom() -> str:
    """
    Scroll the page to the very bottom.

    Returns:
        Scroll confirmation
    """
    page = await pw_manager.ensure_browser()
    logger.info('Scrolling to bottom of page')

    try:
        # Use smooth scrolling for better user experience
        await page.evaluate("""() => {
            window.scrollTo({
                top: document.body.scrollHeight,
                left: 0,
                behavior: 'smooth'
            });
        }""")

        # Small wait to allow smooth scrolling to complete
        await asyncio.sleep(0.5)
        return 'Scrolled to bottom of page'
    except Exception as e:
        error_msg = f'Failed to scroll to bottom: {str(e)}'
        logger.error(error_msg)
        return error_msg


@mcp.tool(
    name='Browser-Scroll-To-Element',
    description='Scroll the page until the specified element is in view.'
)
async def browser_scroll_to_element(selector: str) -> str:
    """
    Scroll the page until the specified element is in view.

    Args:
        selector: CSS or XPath selector for the element to scroll to

    Returns:
        Scroll confirmation
    """
    if not selector or not isinstance(selector, str):
        return 'Error: Selector must be a non-empty string'

    page = await pw_manager.ensure_browser()
    logger.info(f'Scrolling to element with selector: {selector}')

    try:
        # First check if the element exists
        element = await page.query_selector(selector)
        if not element:
            return f'Error: No element found with selector: {selector}'

        # Scroll element into view with smooth behavior
        await page.evaluate(f"""
            (selector) => {{
                const element = document.querySelector(selector);
                if (element) {{
                    element.scrollIntoView({{
                        behavior: 'smooth',
                        block: 'center'
                    }});
                }}
            }}
        """, selector)

        # Small wait to allow smooth scrolling to complete
        await asyncio.sleep(0.5)
        return f"Scrolled to element with selector '{selector}'"
    except Exception as e:
        error_msg = f'Failed to scroll to element: {str(e)}'
        logger.error(error_msg)
        return error_msg
    

@mcp.tool(
    name='Get-Current-URL',
    description='Get the current URL of the browser page.'
)
async def get_current_url() -> str:
    """
    Get the current URL of the browser page.

    Returns:
        Current URL
    """
    page = await pw_manager.ensure_browser()
    logger.info('Getting current URL')

    try:
        url = page.url
        return url
    except Exception as e:
        error_msg = f'Failed to get current URL: {str(e)}'
        logger.error(error_msg)
        return error_msg
    
@mcp.tool(
    name='Get-Element-HTML',
    description='Get the HTML content of a specific element using XPath.'
)
async def get_element_html(xpath: str) -> str:
    """
    Get the HTML content of a specific element using XPath.

    Args:
        xpath: XPath query to find the element

    Returns:
        HTML content of the element or error message
    """
    if not xpath or not isinstance(xpath, str):
        return 'Error: XPath must be a non-empty string'

    page = await pw_manager.ensure_browser()
    logger.info(f'Getting HTML content from element with XPath: {xpath}')

    try:
        element = await page.query_selector(f'xpath={xpath}')
        if not element:
            return f'Error: No element found with XPath: {xpath}'

        html_content = await element.inner_html()
        return html_content
    except Exception as e:
        error_msg = f'Error getting element HTML: {str(e)}'
        logger.error(error_msg)
        return error_msg
    
@mcp.tool(
    name='Get-Element-Text',
    description='Get the text content of an element using XPath.'
)
async def get_element_text(xpath: str) -> str:
    """
    Get the text content of an element using XPath.

    Args:
        xpath: XPath query to find the element

    Returns:
        Text content of the element or error message
    """
    if not xpath or not isinstance(xpath, str):
        return 'Error: XPath must be a non-empty string'

    page = await pw_manager.ensure_browser()
    logger.info(f'Getting text from element with XPath: {xpath}')

    try:
        element = await page.query_selector(f'xpath={xpath}')
        if not element:
            return f'Error: No element found with XPath: {xpath}'

        text = await element.inner_text()
        return text
    except Exception as e:
        error_msg = f'Error getting element text: {str(e)}'
        logger.error(error_msg)
        return error_msg
    
@mcp.tool(
    name='Get-Page-Content',
    description='Get the text content of the current page.'
)
async def get_page_content() -> str:
    """
    Get the text content of the current page.

    Returns:
        Text content of the page
    """
    page = await pw_manager.ensure_browser()
    text_content = await page.evaluate("""() => {
        return document.body.innerText;
    }""")
    return text_content

@mcp.tool(
    name='Get-Page-HTML',
    description='Get the HTML content of the current page.'
)
async def get_page_html() -> str:
    """
    Get the HTML content of the current page.

    Returns:
        HTML content of the page
    """
    page = await pw_manager.ensure_browser()
    html_content = await page.content()
    return html_content

@mcp.tool(
    name='Get-Page-Title',
    description='Get the title of the current page.'
)
async def get_page_title() -> str:
    """
    Get the title of the current page.

    Returns:
        Page title
    """
    page = await pw_manager.ensure_browser()
    title = await page.title()
    return title

@mcp.tool(
    name='Save-Element-As-HTML',
    description="Save a specific element's HTML content to a file using XPath."
)
async def save_element_as_html(xpath: str, file_path: str = None) -> str:
    """
    Save a specific element's HTML content to a file using XPath.

    Args:
        xpath: XPath query to find the element
        file_path: Optional path to save the HTML file. If not provided, a default path will be used.

    Returns:
        Path to the saved HTML file
    """
    if not xpath or not isinstance(xpath, str):
        return 'Error: XPath must be a non-empty string'

    page = await pw_manager.ensure_browser()
    logger.info(f'Saving HTML content of element with XPath: {xpath}')

    if not file_path:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_path = os.path.join(work_dir, f'element_{timestamp}.html')

    try:
        element = await page.query_selector(f'xpath={xpath}')
        if not element:
            return f'Error: No element found with XPath: {xpath}'

        html_content = await element.evaluate('(node) => node.outerHTML')
        if not html_content:
            return f'Error: Could not extract HTML from element with XPath: {xpath}'

        with open(file_path, 'w') as f:
            f.write(html_content)

        return f'HTML content saved to {file_path}'
    except Exception as e:
        error_msg = f'Error saving element HTML: {str(e)}'
        logger.error(error_msg)
        return error_msg
    
@mcp.tool(
    name='Save-Page-As-HTML',
    description="Save the current page's HTML content to a file."
)
async def save_page_as_html(file_path: str = None) -> str:
    """
    Save the current page's HTML content to a file.

    Args:
        file_path: Optional path to save the HTML file. If not provided, a default path will be used.

    Returns:
        Path to the saved HTML file
    """
    page = await pw_manager.ensure_browser()
    logger.info('Saving current page as HTML')

    if not file_path:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_path = os.path.join(work_dir, f'page_{timestamp}.html')

    try:
        html_content = await page.content()
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
    except Exception as e:
        error_msg = f'Failed to save HTML: {str(e)}'
        logger.error(error_msg)
        return error_msg

    return f'HTML saved to {file_path}'

@mcp.tool(
    name='Save-Page-Screenshot',
    description='Save a screenshot of the current page.'
)
async def save_page_screenshot(file_path: str = None) -> str:
    """
    Save a screenshot of the current page.

    Args:
        file_path: Optional path to save the screenshot. If not provided, a default path will be used.

    Returns:
        Path to the saved screenshot
    """
    page = await pw_manager.ensure_browser()
    logger.info('Taking screenshot of the current page')

    if not file_path:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_path = os.path.join(work_dir, f'screenshot_{timestamp}.png')
    else:
        file_path = os.path.join(file_path)

    try:
        await page.screenshot(path=file_path)
    except Exception as e:
        error_msg = f'Failed to take screenshot: {str(e)}'
        logger.error(error_msg)
        return error_msg

    return f'Screenshot saved to {file_path}'

@mcp.tool(
    name='Clear-Field',
    description='Clear the content of a specific input field using XPath.'
)
async def clear_field(xpath: str) -> str:
    """
    Clear the content of a specific input field using XPath.

    Args:
        xpath: XPath query to find the input field

    Returns:
        Confirmation message or error message
    """
    if not xpath or not isinstance(xpath, str):
        return 'Error: XPath must be a non-empty string'

    page = await pw_manager.ensure_browser()
    logger.info(f'Clearing content of input field with XPath: {xpath}')

    try:
        element = await page.query_selector(f'xpath={xpath}')
        if not element:
            return f'Error: No input field found with XPath: {xpath}'

        await element.fill('')  # Clear the field by filling it with an empty string
        return f'Cleared content of input field with XPath: {xpath}'
    except Exception as e:
        error_msg = f'Failed to clear input field: {str(e)}'
        logger.error(error_msg)
        return error_msg
    
@mcp.tool(
    name='Browser-Press-Key',
    description='Press a key on the keyboard.'
)
async def browser_press_key(key: str) -> str:
    """
    Press a key on the keyboard.

    Args:
        key: Key to press (e.g., 'Enter', 'Tab', 'ArrowDown')

    Returns:
        Key press confirmation
    """
    if not key or not isinstance(key, str):
        return 'Error: Key must be a non-empty string'

    page = await pw_manager.ensure_browser()
    logger.info(f'Pressing key: {key}')

    try:
        await page.keyboard.press(key)
    except Exception as e:
        error_msg = f'Error pressing key: {str(e)}'
        logger.error(error_msg)
        return error_msg

    return f"Pressed key {key}"

@mcp.tool(
    name='Browser-Scroll-One-Step',
    description='Scroll the page by one step.'
)
async def browser_scroll_one_step(step: int = 100) -> str:
    """
    Scroll the page by one step.

    Args:
        step: The number of pixels to scroll. Positive for down, negative for up.

    Returns:
        Scroll confirmation message.
    """
    if not isinstance(step, int):
        return 'Error: Step must be an integer'

    page = await pw_manager.ensure_browser()
    logger.info(f'Scrolling the page by {step} pixels')

    try:
        await page.evaluate(f'window.scrollBy(0, {step})')
        return f'Scrolled the page by {step} pixels'
    except Exception as e:
        error_msg = f'Failed to scroll the page: {str(e)}'
        logger.error(error_msg)
        return error_msg
    
@mcp.tool(
    name='Clear-Browser-Data',
    description='Clear cookies, localStorage, and sessionStorage.'
)
async def clear_browser_data() -> str:
    """
    Clear cookies, localStorage, and sessionStorage.

    Returns:
        Confirmation message
    """
    page = await pw_manager.ensure_browser()
    logger.info('Clearing browser data')

    await page.context.clear_cookies()
    await page.evaluate('() => { localStorage.clear(); sessionStorage.clear(); }')

    return 'Browser data cleared'

import json
@mcp.tool(
    name='Get-Cookies',
    description='Get all cookies for the current page.'
)
async def get_cookies() -> str:
    """
    Get all cookies for the current page.

    Returns:
        JSON string of cookies
    """
    page = await pw_manager.ensure_browser()
    logger.info('Getting cookies')

    cookies = await page.context.cookies()
    return json.dumps(cookies, indent=4)

@mcp.tool(
    name='Login-to-Github',
    description='Logs into GitHub and creates a session.'
)
async def login_to_github(username: str, password: str ) -> str:
    """
    Logs into GitHub and stores the authenticated page object.
    
    Args:
        username: Your GitHub username
        password: Your GitHub password
        
    Returns:
        Confirmation message or error message
    """
    page = await pw_manager.ensure_browser()
    
    logger.info("Navigating to GitHub login page...")
    await page.goto("https://github.com/login")
    try:
        await page.wait_for_selector('xpath=//*[@id="login_field"]')
        
        logger.info("Filling in username...")
        await browser_fill('xpath=//*[@id="login_field"]', username)
        
        logger.info("Filling in password...")
        await browser_fill('xpath=//*[@id="password"]', password)
        
        logger.info("Submitting login form...")
        await browser_click('xpath=/html/body/div[1]/div[3]/main/div/div[2]/form/div[3]/input')
        
        await page.wait_for_url("https://github.com/", timeout=15000)
        
        if "Incorrect username or password." in await get_element_text('xpath=//*[@id="js-flash-container"]/div/div/div'):
            return "Error: Incorrect username or password."
        
        logger.info("Login successful.")
        return "Logged into GitHub successfully."
    except Exception as e:
        error_msg = f"Login failed: {str(e)}"
        logger.error(error_msg)
        return error_msg
    

@mcp.tool(
    name='Create-Github-Repo',
    description='Create a new GitHub repository.'
)
async def create_github_repo(repo_name: str, private: bool = False, description: str = "") -> str:
    """
    Create a new GitHub repository.

    Args:
        repo_name: Name of the repository
        private: Whether the repository should be private
        description: Description of the repository

    Returns:
        Confirmation message or error message
    """
    page = await pw_manager.ensure_browser()
    
    logger.info(f"Navigating to new repository page to create '{repo_name}'...")
    await page.goto("https://github.com/new")
    
    try:
        # Wait for the repository name input field to be visible
        await page.wait_for_selector('xpath=//*[@id="repository-name-input"]')
        
        logger.info(f"Filling in repository name: '{repo_name}'")
        await browser_fill('xpath=//*[@id="repository-name-input"]', repo_name)
        
        if description:
            logger.info("Adding repository description.")
            await browser_fill('xpath=//*[@id="repository-description-input"]', description)
        
        if private:
            logger.info("Setting repository to private.")
            private_radio_selector = 'input[type="radio"][value="private"]'
            await browser_click(private_radio_selector)
        asyncio.sleep(1)
        # Wait for the availability check to finish
        if get_element_text('xpath=//*[@id="RepoNameInput-check"]') == "is available." or page.wait_for_selector('xpath=//*[@id="RepoNameInput-is-available"]'):
            create_button_selector = 'xpath=/html/body/div[1]/div[6]/main/react-app/div/form/div[4]/button'
            await browser_click(create_button_selector)
            
            await page.wait_for_selector(f'xpath=//*[@id="repo-title-component"]/strong/a')

            current_url = page.url
            if repo_name in current_url:
                return f"Repository '{repo_name}' created successfully on GitHub at {current_url}"
            else:
                return f"Failed to create repository '{repo_name}': unexpected URL {current_url}"
        else:
            # Check if the name is available before trying to click the button
            availability_status = await page.inner_text('div#RepoNameInput-check')
            if "is available" not in availability_status:
                return f"Error: Repository name '{repo_name}' is not available."

        

    except Exception as e:
        error_msg = f"Failed to create repository '{repo_name}': {str(e)}"
        logger.error(error_msg)
        return error_msg
    

if __name__ == "__main__":
    mcp.run(transport='stdio')
