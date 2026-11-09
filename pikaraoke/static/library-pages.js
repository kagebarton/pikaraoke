// Helpers the library pages share: Processing, Song Info, Repair lyrics, the run preview,
// the pick pass and Add playlist. Each page loads this before its own script; the SPA
// loads it once. The (i) notes' script is info-tip.js, loaded by base.html on every page.
window.libraryPages = {
  // A translated template's {name} slots filled from vars; an unknown name stays as it is.
  fill: function (template, vars) {
    return template.replace(/\{(\w+)\}/g, function (m, name) {
      return vars[name] != null ? vars[name] : m;
    });
  },

  // A new element holding text, never markup.
  el: function (tag, className, text) {
    var node = $('<' + tag + '>');
    if (className) node.addClass(className);
    if (text != null) node.text(text);
    return node;
  },

  // A Genius hit's artist line: "Artist (Year)", the year left off when Genius has none.
  byline: function (hit) {
    return hit.year ? hit.artist + ' (' + hit.year + ')' : hit.artist;
  },

  // /lyrics_search's parameters for a Genius box that started on a song's own search
  // (start: {file_title, query}). The box as it started asks the server to read the file
  // title and run its whole ladder; text the admin edited goes as typed.
  geniusParams: function (text, start) {
    var query = $.trim(text);
    return query === $.trim(start.query) ? { title: start.file_title } : { q: query };
  },

  // The hit id to select when /lyrics_search's answer has a preselect: the song's own Genius
  // pick instead when the list has it (the first of `own` listed; nulls are skipped), so a
  // search never swaps out a pick the song already has. Null when nothing is preselected.
  geniusSelected: function (found, own) {
    if (found.preselect === null) return null;
    var listed = $.map(found.hits, function (hit) { return hit.id; });
    var mine = $.grep(own, function (id) { return id != null && listed.indexOf(id) >= 0; });
    return mine.length ? mine[0] : found.preselect;
  },

  // The server's error message from a failed request, or the fallback.
  errorOf: function (xhr, fallback) {
    try { return JSON.parse(xhr.responseText).error || fallback; } catch (err) { return fallback; }
  }
};
