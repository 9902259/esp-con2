# Automated builds and releases

GitHub Actions tests Python 3.15 and Go on Linux, macOS ARM64 and Windows AMD64.
It builds the single Go CLI/MCP executable, TypeScript website and unified ESP32-S3
firmware using the pinned SDK. Tests use mock transports, not physical consoles.

Push a version tag after pushing the project to GitHub:

```sh
git tag v0.1.0
git push origin v0.1.0
```

Only successful tag builds publish releases. Tags containing a hyphen, such as
`v0.1.0-beta.1`, publish prereleases. Normal pushes, pull requests and manual runs
produce downloadable Actions artifacts without publishing a release.

Release assets contain three native Go binary ZIPs, Python sources (Python 3.15
and requirements installation still required), the compiled website, firmware
images with flash arguments, and `SHA256SUMS`. Extract firmware files together
and follow the included instructions. Release archives never include NVS/bonds,
local SDK installations, caches or backups.

The workflow uses the repository's built-in token; no release secret is required.
Allow Actions in repository settings. The release job alone requests contents
write permission. Workflow definitions must be pushed before GitHub can run them.
