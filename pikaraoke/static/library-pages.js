// Helpers the library pages share: Processing, Song Info, Repair lyrics, the run preview,
// the pick pass and Add playlist. Each page loads this before its own script; the SPA
// loads it once.
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

// The (i) notes (templates/info_tip.html): a hover shows one, a tap pins it open until a
// tap elsewhere. Bound once on the document, so notes the pages render later work too.
(function () {
  var EDGE = 8; // px kept clear of the window's edges
  var GAP = 6;  // px between the button and its note

  // Below the button, or above it when there is no room below; never past an edge.
  function place(tip) {
    var button = tip.find('.info-tip-btn')[0].getBoundingClientRect();
    var note = tip.find('.info-tip-text');
    var width = note.outerWidth();
    var height = note.outerHeight();
    var view = document.documentElement;
    var left = Math.max(EDGE, Math.min(button.left + button.width / 2 - width / 2, view.clientWidth - width - EDGE));
    var top = button.bottom + GAP;
    if (top + height > view.clientHeight - EDGE && button.top - GAP - height >= EDGE) {
      top = button.top - GAP - height;
    }
    note.css({ left: left, top: top });
  }

  function close(tips) {
    tips.removeClass('is-open is-pinned').find('.info-tip-btn').attr('aria-expanded', 'false');
  }

  function closeAll() {
    close($('.info-tip.is-open'));
  }

  // A page re-rendering around an open note can move its button or hide it: the note
  // follows its button, or closes with it. Watching stops once no note is open.
  var watcher = new MutationObserver(function () {
    var tips = $('.info-tip.is-open');
    if (!tips.length) { watcher.disconnect(); return; }
    tips.each(function () {
      var tip = $(this);
      if (tip.find('.info-tip-btn').is(':visible')) place(tip); else close(tip);
    });
  });

  // A tap closes every other note; a hover leaves a pinned one open.
  function open(tip, pin) {
    var others = $('.info-tip.is-open').not(tip);
    close(pin ? others : others.not('.is-pinned'));
    tip.addClass('is-open').toggleClass('is-pinned', pin || tip.hasClass('is-pinned'));
    tip.find('.info-tip-btn').attr('aria-expanded', 'true');
    place(tip);
    // The notes' own style writes are left out, so placing one does not wake the watcher.
    watcher.observe(document.body, { subtree: true, childList: true, characterData: true, attributeFilter: ['class'] });
  }

  // Both stop the click before page handlers delegated on the document see it. A handler
  // bound on the row or tab itself runs first, so it skips clicks from inside .info-tip.
  $(document).on('click.infotip', '.info-tip-btn', function (e) {
    e.preventDefault();
    e.stopPropagation();
    var tip = $(this).closest('.info-tip');
    if (tip.hasClass('is-pinned')) close(tip); else open(tip, true);
  });
  $(document).on('click.infotip', '.info-tip-text', function (e) {
    e.preventDefault();
    e.stopPropagation();
  });
  $(document).on('click.infotip', closeAll);
  $(document).on('keydown.infotip', function (e) {
    if (e.key === 'Escape') closeAll();
  });
  // A scroll or resize counts as moving on, as a tap elsewhere does.
  window.addEventListener('scroll', closeAll, true);
  $(window).on('resize.infotip', closeAll);

  if (window.matchMedia('(hover: hover)').matches) {
    $(document).on('mouseenter.infotip', '.info-tip', function () {
      var tip = $(this);
      clearTimeout(tip.data('hoverClose'));
      if (!tip.hasClass('is-open')) open(tip, false);
    });
    // A short delay lets the pointer cross the gap between the button and its note.
    $(document).on('mouseleave.infotip', '.info-tip', function () {
      var tip = $(this);
      if (!tip.hasClass('is-pinned')) tip.data('hoverClose', setTimeout(function () { close(tip); }, 150));
    });
  }
})();
