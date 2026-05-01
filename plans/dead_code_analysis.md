# Dead/Orphaned Code Analysis (lib folder)

This document contains the findings from the static analysis of the `lib/` directory and core orchestrator files. 

## Overview
All 23 files within the `lib/` directory are actively imported and utilized somewhere in the project pipeline. **No entire file in the `lib` directory is completely orphaned or dead.** The separation of concerns appears intact.

## Dead Code / Unused Entities
The following methods, functions, and properties appear to be deprecated or abandoned as features were added and removed over time:

### `lib/karaoke_database.py`
- `get_song_count()`: A helper method that is defined but never called anywhere in the codebase.
- `get_loudnorm_offset()`: Defined but completely unused.
- `check_integrity()`: Database integrity check method that is never invoked.
- `row_factory`: Class attribute that is assigned but never utilized.

### `lib/mpv_controller.py`
This class retains some state-tracking variables and helper methods from older iterations of MPV integration:
- `_toggle_fullscreen()`: Inner function that was written but is never called.
- `get_system_volume()`: Method defined but never used to poll the system volume.
- **Unused tracking attributes**: `_current_pitch`, `duration_ready`, `lavfi_complex`, `prev_mode`, `sid`, and `sub_delay`. These are populated internally during state changes but their values are never actually read or used elsewhere.

### `lib/metadata_parser.py`
- `clear_song_name_cache()`: Function defined but never used. (It is imported in `routes/batch_song_renamer.py` but never actually invoked).

### `lib/get_platform.py`
- `is_running_in_docker()`: Helper function that is never checked or utilized by the rest of the application.

### `lib/playback_controller.py`
- `now_playing_filename`: Property frequently assigned updated values but completely unreferenced/unused by the rest of the system.
- `now_playing_position`: Property frequently assigned updated values but completely unreferenced/unused by the rest of the system.

### `lib/processing_manager.py`
- `intermediate_dir`: Attribute assigned in the constructor but never referenced in any of the processing logic.

### Core Orchestrator Files
#### `karaoke.py`
- `blocked_processing_words`: In the `__init__` constructor, this parameter (`blocked_processing_words: str | None = None` on Line 107) is defined but never used or assigned to class state anywhere inside the application.

*Note: Route endpoints in the `routes/` directory (e.g. `update_ytdl()`, `delete_file()`) naturally appear as "unused" to static analysis because Flask dynamically registers and calls these functions via decorators. They are completely normal and not dead code.*
