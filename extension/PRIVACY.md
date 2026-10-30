# Privacy Policy - BlockTrace Verifier

*Last updated: October 29, 2026*

The **BlockTrace Verifier** browser extension is designed with a strict privacy-first architecture. It operates exclusively on user request and does not track, collect, or store your browsing activity.

## What is Processed

1. **Forensic Report Verification**: When you choose to upload a PDF report for verification, the file and the investigation hash are transmitted directly to the configured BlockTrace verification API (`https://blocktrace-v2.onrender.com/report/verify`). The file is processed entirely in volatile server memory to compute cryptographic SHA-256 digests and compare them with public on-chain Sepolia records. The file is never written to disk, retained, or logged.
2. **Address Sanctions Check**: When you enter an Ethereum address or select text and invoke the context menu "Check address with BlockTrace", that single address is queried against BlockTrace's dated snapshot of the OFAC SDN list. No search history or query logs are retained.

## What is NOT Collected

- **No browsing activity, history, or URLs visited**
- **No analytics, telemetry, or tracking scripts**
- **No cookies or persistent tracking identifiers**
- **No personal identity data**
- **No advertising network integration**
- **No data selling or sharing with third parties**

## Permissions Justification

- **`storage`**: Used solely to read and cache configuration (such as the API base URL) locally within your browser.
- **`contextMenus`**: Allows you to highlight an Ethereum address on any web page and right-click "Check address with BlockTrace" to quickly screen it in a popup.
- **Host Permission (`https://blocktrace-v2.onrender.com/*`)**: Required exclusively to make HTTPS requests to the BlockTrace verification and sanctions API endpoints.

## Published Privacy Policy

The same text is published online and accessible at:
[https://blocktrace-v2.vercel.app/privacy](https://blocktrace-v2.vercel.app/privacy)

## Contact

BlockTrace is an open forensic investigation and verification platform. For inquiries or vulnerability disclosures, please open an issue on the project repository or contact the BlockTrace maintenance team.

