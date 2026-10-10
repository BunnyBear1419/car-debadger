# Car-Debadger — FiveM Vehicle Debadger

A Windows desktop utility for auditing large FiveM vehicle-resource collections and preparing safe debadging workspaces.

## Install from a build

1. Open the repository's **Actions** tab.
2. Select the latest successful **Windows Desktop Build** run.
3. Under **Artifacts**, download `Car-Debadger-Windows` and extract it.
4. Run `Car-Debadger-Setup.exe` to install. Windows may display a SmartScreen warning because this community build is not code-signed; only run builds you trust and downloaded from this repository.

The workflow creates a Windows installer whenever changes are pushed to `main` or `feature/windows-installer`. Build artifacts are retained for 30 days. A successful workflow run is required before an installer is available.

## Build locally on Windows

Requirements: Python 3.12 or newer and Inno Setup 6.

1. Clone or download this repository.
2. Run `build_windows.bat`.
3. After the portable app is built, run `ISCC.exe installer\\Car-Debadger.iss` from the repository root to create `dist\\installer\\Car-Debadger-Setup.exe`.

## What it does

- Scans `.yft`, `.ytd`, common image textures, vehicle metadata, and resource manifests.
- Displays asset inventory with filtering, file sizes, and SHA-256 fingerprints.
- Creates a separate workspace copy, texture/model review queues, and JSON/CSV readiness reports.
- Keeps source files untouched during scanning and workspace creation.

## Important limitations

This application is an inventory and workflow assistant, not an automatic 3D badge-removal engine. Vehicle badges may be part of a model mesh or embedded in a texture dictionary. The app does not claim to remove those automatically; use compatible GTA V/FiveM asset tools for edits and validate changes on a local test server before deployment. Never test changes directly on your live server resources.

## Troubleshooting

- If Windows blocks an unsigned installer, verify it came from this repository before choosing whether to run it.
- If the app fails to launch, download the latest successful workflow artifact and check the workflow log for packaging errors.
- Keep a separate backup of original vehicle resources before editing assets.
