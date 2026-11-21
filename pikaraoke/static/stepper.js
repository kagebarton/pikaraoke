// The shared slider's behaviour (templates/stepper.html). base.html loads this on every page
// (and stepper.css beside it), so a stepper works wherever a page renders one. Don't load it
// again from a page: every handler below would be bound twice.
//
// A stepper is drawn when it is given a value: by a drag, a tap, or stepperSet. A page gives
// its steppers their first value from its own state before it shows them.
(function () {
  // How the knob writes a value, by the stepper's data-format.
  var FORMATS = {
    percent: function (v) { return Math.round(v) + '%'; },
    semitones: function (v) { return (v > 0 ? '+' : '') + v; },
    seconds: function (v) { return (v > 0 ? '+' : '') + (v ? v.toFixed(1) : '0') + ' s'; }
  };

  function decimals(step) {
    var dot = String(step).indexOf('.');
    return dot < 0 ? 0 : String(step).length - dot - 1;
  }

  // Where the value sits on the rail (--frac), where 0 sits (--zero, kept on the rail), and the
  // fill's two ends (--lo, --hi): between 0 and the value. The knob shows the value; the - and
  // + buttons are disabled at their end.
  function paint(range) {
    var stepper = range.closest('.stepper');
    var min = +range.min;
    var max = +range.max;
    var value = +range.value;
    var frac = (value - min) / (max - min);
    var zero = Math.min(1, Math.max(0, -min / (max - min)));
    var text = FORMATS[stepper.dataset.format](value);
    stepper.style.setProperty('--frac', frac);
    stepper.style.setProperty('--zero', zero);
    stepper.style.setProperty('--lo', Math.min(frac, zero));
    stepper.style.setProperty('--hi', Math.max(frac, zero));
    stepper.querySelector('.stepper-knob').textContent = text;
    range.setAttribute('aria-valuetext', text);
    stepper.querySelector('[data-dir="-1"]').disabled = value <= min;
    stepper.querySelector('[data-dir="1"]').disabled = value >= max;
  }

  // A tap moves the range one tap and fires the events a drag would, so a page's own handlers
  // treat the two alike. The input event is what repaints.
  $(document).on('click.stepper', '.stepper-btn', function () {
    var stepper = this.closest('.stepper');
    var range = stepper.querySelector('.stepper-range');
    var before = +range.value;
    var moved = before + this.dataset.dir * stepper.dataset.tap;
    range.value = Math.min(+range.max, Math.max(+range.min, moved)).toFixed(decimals(range.step));
    if (+range.value === before) return;
    range.dispatchEvent(new Event('input', { bubbles: true }));
    range.dispatchEvent(new Event('change', { bubbles: true }));
  });

  $(document).on('input.stepper', '.stepper-range', function () { paint(this); });

  // Sets a stepper from the server or a form. It fires no events, so a page's send handler
  // never echoes a server push back. A page without the stepper (the admin's, on a guest's
  // phone) passes null.
  window.stepperSet = function (range, value) {
    if (!range) return;
    range.value = value;
    paint(range);
  };
})();
