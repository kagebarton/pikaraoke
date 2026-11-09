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

  // The server's error message from a failed request, or the fallback.
  errorOf: function (xhr, fallback) {
    try { return JSON.parse(xhr.responseText).error || fallback; } catch (err) { return fallback; }
  }
};
