# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **`FORCE_EXCLUSION_LIST_REFRESH` option** ([#14](https://github.com/4lx69/jellyfin-collection/issues/14)): Radarr/Sonarr exclusion lists and blocklists are only fetched once, at startup. In the scheduler daemon this means items excluded after launch keep being requested on every subsequent run until the container is restarted. Set `FORCE_EXCLUSION_LIST_REFRESH=true` (or `settings.force_exclusion_list_refresh: true` in `config.yml`) to re-fetch both lists at the start of every run. Disabled by default, so the existing behavior is unchanged.

### Fixed

- **Accurate Radarr/Sonarr request counts**: Items that Radarr/Sonarr declined to add (excluded, blocklisted, or not found) were still counted as requested and listed in run reports and notifications. They are now excluded from the counts.

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
