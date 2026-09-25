# End-to-end tests

End-to-end tests use Playwright to test widgets and components in the browser.

## Structure

Test modules (`test_*.py`) are accompanied by IPython scripts (`test_*.ipy`)
that expose the tested functionality.
These scripts are rendered by Voila as webpages and tested by the modules.

## Debugging

Run `pytest` with the `PWDEBUG=1` environment variable to interactively debug
Playwright tests (see [docs][pwdebug]).

[pwdebug]: https://playwright.dev/python/docs/debug#run-in-debug-mode
