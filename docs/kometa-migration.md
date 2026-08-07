# Migrating from Kometa / Plex Meta Manager

This guide helps you migrate your existing Kometa or Plex Meta Manager configuration to JFC.

## Overview

JFC is designed to be largely compatible with Kometa YAML configurations. Most configurations will work with minimal changes.

## Migration Steps

### 1. Copy Configuration Files

Copy your Kometa configuration files to the JFC config directory:

```bash
# Copy main config
cp /path/to/kometa/config/config.yml ./config/

# Copy collection files
cp /path/to/kometa/config/*.yml ./config/
```

### 2. Update Library Names

Update library names in `config.yml` to match your **Jellyfin** library names exactly:

```yaml
# Before (Plex library names)
libraries:
  Movies:
    collection_files:
      - file: config/Movies.yml

# After (Jellyfin library names)
libraries:
  Films:                            # Must match Jellyfin exactly
    collection_files:
      - file: config/Films.yml
```

### 3. Remove Plex-Specific Settings

Remove settings that are specific to Plex:

```yaml
# Remove these sections
plex:
  url: ...
  token: ...

# Remove Plex-specific collection settings
collections:
  "My Collection":
    # Remove:
    # - plex_all
    # - plex_pilots
    # - plex_collectionless
    # - smart_filter
    # - smart_url
```

### 4. Update Builders

Most builders are supported. Here's the mapping:

| Kometa Builder | JFC Support | Notes |
|----------------|-------------|-------|
| `tmdb_trending_weekly` | ✅ Supported | - |
| `tmdb_trending_daily` | ✅ Supported | - |
| `tmdb_popular` | ✅ Supported | - |
| `tmdb_discover` | ✅ Supported | - |
| `tmdb_now_playing` | ✅ Supported | - |
| `trakt_trending` | ✅ Supported | - |
| `trakt_popular` | ✅ Supported | - |
| `trakt_chart` | ✅ Supported | - |
| `trakt_list` | ✅ Supported | - |
| `plex_search` | ✅ Supported | Jellyfin library search (`Genres`, `year`, `year.gte`, `year.lte`, `limit`) |
| `mdblist_list` | ✅ Supported | URL / user/slug / numeric ID; dict with `limit`, `sort_by` |
| `imdb_chart` | ✅ Supported | top, boxoffice, moviemeter, tvmeter |
| `imdb_list` | ✅ Supported | `ls...` lists |
| `tmdb_list` | ✅ Supported | ID/string/URL accepted |
| `radarr_taglist` | ✅ Supported | Build movie collections from Radarr tags |
| `sonarr_taglist` | ✅ Supported | Build series collections from Sonarr tags |
| `letterboxd_list` | ❌ Not supported | - |
| `reciperr_list` | ❌ Not supported | - |

### 5. Update Templates

Templates work the same way, but remove Plex-specific options:

```yaml
# Before
templates:
  movie:
    sync_mode: sync
    collection_mode: hide
    visible_library: false
    visible_home: false
    visible_shared: false

# After
templates:
  movie:
    sync_mode: sync
    # collection_mode, visible_* not applicable in Jellyfin
```

### 6. Validate Configuration

Run validation to check for issues:

```bash
jfc validate --config ./config
```

### 7. Test with Dry Run

Preview what will happen without making changes:

```bash
jfc run --config ./config --dry-run
```

## Common Changes

### Overlays

JFC does not support overlays. Remove overlay configurations:

```yaml
# Remove these
overlay_files:
  - file: config/overlays.yml
```

### Collection Mode

Jellyfin doesn't have the same collection visibility options. Remove:

```yaml
# Remove from collections
collection_mode: hide
visible_library: false
visible_home: false
visible_shared: false
```

### Smart Collections

Smart collections / smart filters are Plex-specific. Convert to regular collections with filters:

```yaml
# Before (Plex smart collection)
collections:
  "4K Movies":
    smart_filter:
      all:
        resolution: 4k

# After (JFC with a supported source builder)
collections:
  "4K Movies":
    tmdb_discover:
      sort_by: popularity.desc
      limit: 50
```

### Metadata

JFC focuses on collections, not metadata management. Remove:

```yaml
# Remove
metadata_files:
  - file: config/metadata.yml
```

## Example Migration

### Original Kometa Config

```yaml
# config.yml (Kometa)
libraries:
  Movies:
    collection_files:
      - file: config/Movies.yml
    overlay_files:
      - file: config/Overlays.yml
    metadata_files:
      - file: config/Metadata.yml

plex:
  url: http://plex:32400
  token: xxxx

tmdb:
  apikey: xxxx
  language: en
```

### Migrated JFC Config

```yaml
# config.yml (JFC)
libraries:
  Films:                          # Jellyfin library name
    collection_files:
      - file: config/Films.yml
  # Note: overlays and metadata removed
```

### Original Collection File

```yaml
# Movies.yml (Kometa)
templates:
  movie:
    sync_mode: sync
    collection_mode: hide
    visible_library: false

collections:
  "Trending Movies":
    template: {name: movie}
    tmdb_trending_weekly: 20
    summary: "Trending this week"
```

### Migrated Collection File

```yaml
# Films.yml (JFC)
templates:
  movie:
    sync_mode: sync
    # Removed Plex-specific options

collections:
  "Trending Movies":
    template: {name: movie}
    tmdb_trending_weekly: 20
    summary: "Trending this week"
```

## Environment Variables

Create a `.env` file with your API keys:

```bash
# Required
JELLYFIN_URL=http://jellyfin:8096
JELLYFIN_API_KEY=your_jellyfin_key
TMDB_API_KEY=your_tmdb_key        # Same as Kometa

# Optional (same as Kometa)
TRAKT_CLIENT_ID=your_trakt_id
TRAKT_CLIENT_SECRET=your_trakt_secret
RADARR_URL=http://radarr:7878
RADARR_API_KEY=your_radarr_key
SONARR_URL=http://sonarr:8989
SONARR_API_KEY=your_sonarr_key
```

## Troubleshooting

### "Library not found in Jellyfin"

Library names must match exactly (case-sensitive). Check:
1. Jellyfin web UI for exact library name
2. Accented characters (e.g., "Séries" not "Series")

### "Builder not supported"

Check the supported builders list above. Some Plex-specific builders don't have equivalents.

### Collections not updating

1. Check `schedule` setting in collection config
2. Verify `sync_mode: sync` is set
3. Run with `--dry-run` to see what would change

## Next Steps

After migration:
- [Configuration Guide](configuration.md) - Full reference
- [AI Poster Generation](ai-posters.md) - Add AI posters
