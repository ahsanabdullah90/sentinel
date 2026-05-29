"""Search Detector Utility Module

Provides heuristic search input detection using Playwright.
"""

async def detect_search_input(page) -> str:
    """Run heuristic JavaScript on the given Playwright page to locate a search input.

    Args:
        page: The Playwright page instance.

    Returns:
        The CSS selector string for the search field, or empty string if not found.
    """
    return await page.evaluate("""() => {
        const inputs = Array.from(document.querySelectorAll('input[type="text"], input[type="search"], input:not([type])'));
        for (const input of inputs) {
            const id = input.id.toLowerCase();
            const name = (input.getAttribute('name') || '').toLowerCase();
            const placeholder = (input.getAttribute('placeholder') || '').toLowerCase();
            const className = input.className.toLowerCase();
            if (id.includes('search') || id.includes('query') || id.includes('q') ||
                name.includes('search') || name.includes('query') || name.includes('q') ||
                placeholder.includes('search') || placeholder.includes('find') || placeholder.includes('query') ||
                className.includes('search')) {
                if (input.id) return `#${input.id}`;
                const nameAttr = input.getAttribute('name');
                if (nameAttr) return `input[name="${nameAttr}"]`;
                if (input.getAttribute('placeholder')) return `input[placeholder="${input.getAttribute('placeholder')}"]`;
            }
        }
        if (inputs.length > 0) {
            const first = inputs[0];
            if (first.id) return `#${first.id}`;
            const firstName = first.getAttribute('name');
            if (firstName) return `input[name="${firstName}"]`;
        }
        return '';
    }""")
