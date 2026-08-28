# eBay Marketplace Account Deletion notification setup

Production keysets require Marketplace Account Deletion compliance.

Endpoint:
`https://hanamans-pricing-tool.vercel.app/ebay/marketplace-deletion/`

Vercel environment variable:
`EBAY_DELETION_VERIFY_TOKEN`

Use the same 32-80 character verification token in Vercel and the eBay Developer Portal. Allowed characters are alphanumeric, underscore, and hyphen.

The endpoint implements eBay's GET challenge response and acknowledges POST notifications with 204. The app intentionally does not persist deletion-notification payloads or buyer identifiers.
