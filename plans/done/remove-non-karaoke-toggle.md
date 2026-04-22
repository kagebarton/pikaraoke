Model: Claude Opus 4.6

# Remove "Include non-karaoke matches" toggle

## Context

The search UI has an "Include non-karaoke matches" checkbox in the Advanced Settings section. When unchecked (the default), the backend appends `" karaoke"` to every YouTube search query. The user wants unrestricted search to be the only behavior -- removing the toggle entirely and never appending `" karaoke"` to queries.

## Changes

### 1. Backend: simplify search route

**File:** `pikaraoke/routes/search.py` (lines 46-52)

Remove the `non_karaoke` parameter handling. Always call `get_search_results(search_string)` without appending `" karaoke"`:

```python
# Before
non_karaoke = request.args.get("non_karaoke") == "true"
if non_karaoke:
    search_results = get_search_results(search_string)
else:
    search_results = get_search_results(search_string + " karaoke")

# After
search_results = get_search_results(search_string)
```

### 2. Template: remove checkbox and hidden field

**File:** `pikaraoke/templates/search.html`

- **Remove checkbox** (lines 634-638): the `<label>` containing `#include-non-karaoke`
- **Remove hidden form field** (line 676): `<input type="text" id="non_karaoke" name="non_karaoke" />`

### 3. Template: remove JavaScript

**File:** `pikaraoke/templates/search.html`

- **Remove cookie save handler** (lines 430-434): the `$("#include-non-karaoke").change(...)` block
- **Remove cookie restore** (lines 559-563): the "Include non-karaoke matches" section in `restoreCheckboxStates()`
- **Remove from search handler** (lines 342, 348): the `include_non_karaoke` variable and `$("#non_karaoke").val(...)` line

### 4. Translations: remove message

**File:** `pikaraoke/messages.pot` and all `*/LC_MESSAGES/messages.po` files

Remove the `msgid "Include non-karaoke matches"` entry and its translations. There are ~15 locale files.

## Verification

1. Run `pre-commit run --config code_quality/.pre-commit-config.yaml --all-files`
2. Run tests: `/home/ken/miniconda3/envs/pik/bin/python -m pytest`
3. Manual: open the search page, confirm the checkbox is gone from Advanced Settings, and confirm searches return unrestricted results (no `" karaoke"` appended)
