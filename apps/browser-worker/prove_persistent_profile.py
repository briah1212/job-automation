"""Prove the persistent Chrome profile is really being used.

Connects to the real systemd Chrome via CDP (BROWSER_CDP_URL),
opens a new tab, navigates to myaccount.google.com, and reports
what's visible — signed-in account or login prompt.

Run inside the browser-worker container (which can reach host.docker.internal):
  docker compose cp prove_persistent_profile.py browser-worker:/app/
  docker compose exec -e BROWSER_CDP_URL=http://host.docker.internal:9222 browser-worker python /app/prove_persistent_profile.py
"""

import asyncio
import os
import sys

from playwright.async_api import async_playwright


async def main():
    cdp_url = os.environ.get("BROWSER_CDP_URL", "")
    if not cdp_url:
        print("FATAL: BROWSER_CDP_URL not set")
        sys.exit(1)

    print(f"Connecting to: {cdp_url}")

    async with async_playwright() as pw:
        # Connect to the persistent browser — exactly what worker.py does
        browser = await pw.chromium.connect_over_cdp(cdp_url)
        print(f"\nConnected to browser: {browser.version}")

        # Inspect existing context(s)
        contexts = browser.contexts
        print(f"\nExisting contexts before we do anything: {len(contexts)}")

        if contexts:
            ctx = contexts[0]
            print(f"  Context 0 pages before: {len(ctx.pages)}")
            for i, p in enumerate(ctx.pages):
                print(f"    Page {i}: {p.url[:100]}")

            # Open a new tab in the persistent context
            page = await ctx.new_page()
            print(f"\nOpened new tab (should be about:blank): {page.url}")

            # Navigate to Google account
            print("\nNavigating to https://myaccount.google.com/ ...")
            await page.goto("https://myaccount.google.com/", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)

            # Report what we see
            title = await page.title()
            url = page.url
            print(f"\nPage title: {title}")
            print(f"Final URL:  {url}")

            # Key evidence: look for logged-in indicators
            body_text = await page.inner_text("body")
            email_present = "brianhsu1212" in body_text
            sign_in_present = "Sign in" in body_text[:500] or "Sign-In" in body_text[:500]

            print(f"\n--- PROOF: Persistent profile check ---")
            print(f"Email 'brianhsu1212' visible: {email_present}")
            print(f"Sign-in prompt visible:       {sign_in_present}")

            if email_present and not sign_in_present:
                print("VERDICT: REAL PERSISTENT PROFILE — Google is logged in.")
            elif sign_in_present and not email_present:
                print("VERDICT: THROWAWAY PROFILE — Google login prompt shown.")
            else:
                print("VERDICT: AMBIGUOUS — inspect manually.")

            # Also report the contexts/pages count again to show we didn't leak
            print(f"\nContext 0 pages after (our tab should be closed at cleanup): {len(ctx.pages)}")
            for i, p in enumerate(ctx.pages):
                print(f"  Page {i}: {p.url[:100]}")

            # Clean up — close only our tab
            await page.close()
            print(f"\nAfter closing our tab: {len(ctx.pages)} pages remain (should be original count)")

            # Check if other tabs have persisted sessions too
            print(f"\nExisting context cookies: {len(await ctx.cookies())} cookies")
            print("(If > 0, the profile has stored sessions — which is exactly what we want)")

        else:
            print("WARNING: No existing contexts found — this is unexpected for a persistent profile.")
            # Fall back to local mode check
            ctx = await browser.new_context()
            page = await ctx.new_page()
            await page.goto("https://myaccount.google.com/", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)
            body_text = await page.inner_text("body")
            sign_in_present = "Sign in" in body_text[:500]
            print(f"Fallback new context — sign-in prompt: {sign_in_present}")
            await page.close()
            await ctx.close()

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
