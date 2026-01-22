# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] - 2026-01-22

### Fixed

- **Media matcher cache persistence bug**: Fixed an issue where newly added items in Jellyfin were not detected during scheduled runs. The `MediaMatcher` cache was persisting across scheduler runs, causing items added to Jellyfin after the initial run to never be matched. The cache is now reset at the start of each run, ensuring all libraries are reloaded and new items are properly detected.

## [1.0.0] - 2025-12-01

### Added

- Initial release
- Kometa YAML configuration compatibility
- TMDb, Trakt, and MDBList data sources
- Sonarr/Radarr integration for missing media requests
- AI-powered poster generation via OpenAI
- Discord webhook notifications with rich embeds
- Telegram notifications with AI-generated messages
- Signal notifications via signal-cli-rest-api
- Dual scheduler (daily sync + monthly poster regeneration)
- Docker support with multi-platform images
