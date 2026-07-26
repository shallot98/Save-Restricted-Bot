# Current notes filter wiring (2026-07-21)

## Backend (ready)

- `web/routes/notes.py`: parses `source`, `q`/`search`, `date_from`, `date_to`, `favorite=1`
- Search repo supports favorite_only, date range, source_chat_id
- Pagination macro already appends source/search/date/favorite query params

## Frontend gaps

- `templates/notes.html` filter bar:
  - Favorite: Alpine `filterFavorite` toggle only; not bound to server `favorite_only`; does not navigate
  - Date: button only
  - Tag: button only; decision = source filter via existing `sources` template var + `?source=`
- Sidebar already lists sources and favorite; mobile nav has favorite link
- Alpine init around line 555: `filterFavorite: false` hardcoded

## Implementation guidance

1. Initialize Alpine from Jinja: favorite_only, selected_source, date_from, date_to
2. Favorite button: set/clear `favorite=1`, reset page to 1, keep other filters
3. Date panel: two date inputs + apply/clear → navigate with params
4. Tag/source panel: list `sources`, select → `source=`, clear source
5. Helper to build `/notes?...` from current params preferred over partial Alpine-only client filter
6. Avoid new backend unless necessary
