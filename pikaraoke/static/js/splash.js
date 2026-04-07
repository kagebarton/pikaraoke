let socket = io();
let mouseTimer = null;
let cursorVisible = false;
let nowPlaying = {};
let octopusInstance = null;
let showMenu = false;
let menuButtonVisible = false;
let autoplayConfirmed = false;
let volume = 0.85;
const playbackStartTimeout = 10000;
let currentVideoUrl = null;
let hlsInstance = null;
let isMaster = false;
let uiScale = null;
let clockIntervalId = null;

// Browser detection
const isSafari = /^((?!chrome|android).)*safari/i.test(navigator.userAgent);
const isMobileSafari = isSafari && (/iPhone|iPad|iPod/i.test(navigator.userAgent) || navigator.maxTouchPoints > 1);
const isChrome = /chrome/i.test(navigator.userAgent) && !/edg/i.test(navigator.userAgent);
const isFirefox = /firefox/i.test(navigator.userAgent);
const isEdge = /edg/i.test(navigator.userAgent);
const isSupportedBrowser = isSafari || isChrome || isFirefox || isEdge;

const isMediaPlaying = (media) =>
  !!(
    media.currentTime > 0 &&
    !media.paused &&
    !media.ended &&
    media.readyState > 2
  );

const formatTime = (seconds) => {
  if (isNaN(seconds)) {
    return "00:00";
  }
  const totalSeconds = Math.floor(seconds);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const secs = totalSeconds % 60;
  const formattedMinutes = String(minutes).padStart(2, "0");
  const formattedSeconds = String(secs).padStart(2, "0");
  return `${formattedMinutes}:${formattedSeconds}`;
}

const testAutoplayCapability = async () => {
  // Test if autoplay with audio is allowed using a real video file
  try {
    const testVideo = document.createElement('video');
    testVideo.playsInline = true;
    testVideo.muted = true;  // Start muted (always allowed)
    testVideo.src = "/static/video/test_autoplay.mp4";

    // Wait for video to be ready
    await new Promise((resolve, reject) => {
      testVideo.onloadeddata = resolve;
      testVideo.onerror = reject;
    });

    await testVideo.play();
    // Now try to unmute - this is the real test
    testVideo.muted = false;
    testVideo.volume = 0.01;

    // Brief delay to let browser enforce policy
    await new Promise(resolve => setTimeout(resolve, 500));

    // Check if browser paused or muted the video
    if (testVideo.muted || testVideo.paused) {
      testVideo.pause();
      $('#permissions-modal').addClass('is-active');
    } else {
      testVideo.pause();
      handleConfirmation();
    }
  } catch (e) {
    // Autoplay blocked
    console.log("Autoplay error thrown", e);
    $('#permissions-modal').addClass('is-active');
  }
};

const handleConfirmation = () => {
  $('#permissions-modal').removeClass('is-active');
  autoplayConfirmed = true;
  loadNowPlaying();
};

const hideVideo = () => {
  $("#video-container").hide();
}

const endSong = async (reason = null) => {
  currentVideoUrl = null;
  if (hlsInstance) {
    hlsInstance.destroy();
    hlsInstance = null;
  }
  const video = getVideoPlayer();
  video.pause();
  $("#video-source").attr("src", "");
  video.load();
  hideVideo();
  if (isMaster) {
    socket.emit("end_song", reason);
  } else {
    console.log("Slave active (read-only): skipping end_song emission");
  }
}

const getVideoPlayer = () => $("#video")[0]

const flashNotification = (message, categoryClass) => {
  const sn = $("#splash-notification");
  if (sn.html()) return;
  sn.html(message);
  sn.addClass(categoryClass);
  sn.fadeIn();
  setTimeout(() => {
    sn.fadeOut();
    setTimeout(() => {
      sn.html("");
      sn.removeClass(categoryClass);
    }, 450);
  }, 3000);
}

const handleNowPlayingUpdate = (np) => {
  nowPlaying = np;
  if (np.now_playing) {

    // Handle updating now playing HTML
    let nowPlayingHtml = `<span>${np.now_playing}</span> `;
    if (np.now_playing_transpose !== 0) {
      nowPlayingHtml += `<span class='is-size-6 has-text-success'><b>Key</b>: ${getSemitonesLabel(np.now_playing_transpose)} </span>`;
    }
    $("#now-playing-song").html(nowPlayingHtml);
    $("#now-playing-singer").html(np.now_playing_user);
    $("#now-playing").fadeIn();
  } else {
    $("#now-playing").fadeOut();
  }
  if (np.up_next) {
    $("#up-next-song").html(np.up_next);
    $("#up-next-singer").html(np.next_user);
    $("#up-next").fadeIn();
  } else {
    $("#up-next").fadeOut();
  }

  const video = getVideoPlayer();

  // Setup ASS subtitle file if found
  const subtitleUrl = np.now_playing_subtitle_url;
  if (octopusInstance) {
    octopusInstance.dispose();
    octopusInstance = null;
  }
  if (subtitleUrl && video) {
    // Use per-song subtitle delay from now_playing data, or fall back to config default
    const songSubtitleDelay = np.subtitle_delay !== undefined 
      ? np.subtitle_delay 
      : PikaraokeConfig.subtitleDelay;
    const options = {
      video: video,
      subUrl: subtitleUrl,
      fonts: ["/static/fonts/Arial.ttf", "/static/fonts/DroidSansFallback.ttf"],
      debug: true,
      workerUrl: "/static/js/subtitles-octopus-worker.js",
      // Invert the sign: user expects negative = earlier, but timeOffset works opposite
      timeOffset: songSubtitleDelay ? -songSubtitleDelay : 0
    };
    try {
      octopusInstance = new SubtitlesOctopus(options);
      if (uiScale) {
        // Find the canvas created by SubtitlesOctopus (sibling of the video)
        const canvas = video.parentNode.querySelector('canvas');
        if (canvas) {
          canvas.style.transform = `scale(${uiScale})`;
          canvas.style.transformOrigin = 'bottom center';
        }
      }
    } catch (e) { console.error(e); }
  }

  if (np.now_playing_url && np.now_playing_url !== currentVideoUrl) {
    currentVideoUrl = np.now_playing_url;
    const streamUrl = np.now_playing_url;
    $("#video-source").attr("src", "");
    video.load();
    $("#video-source").attr("src", streamUrl);

    if (streamUrl.endsWith('.m3u8')) {
      const useNativeHLS = video.canPlayType('application/vnd.apple.mpegurl') && !isChrome && !isEdge && !isMobileSafari;
      if (useNativeHLS) {
        video.src = streamUrl;
      } else {
        if (hlsInstance) { hlsInstance.destroy(); hlsInstance = null; }
        hlsInstance = new Hls({ startPosition: 0 });
        hlsInstance.loadSource(streamUrl);
        hlsInstance.attachMedia(video);
      }
    }

    video.load();
    if (volume !== np.volume) {
      volume = np.volume;
      video.volume = volume;
    }

    const duration = $("#duration");
    if (np.now_playing_duration) {
      duration.text(`/${formatTime(np.now_playing_duration)}`);
      duration.show();
    } else {
      duration.hide();
    }

    $("#video-container").show();

    video.play().catch(err => {
      console.error('Play failed:', err);
      // Retry once if it was an autoplay block
      setTimeout(() => video.play(), 1000);
    });

    if (np.now_playing_position && isMediaPlaying(video)) {
      if (Math.abs(video.currentTime - np.now_playing_position) > 2) {
        console.log("Syncing to server position:", np.now_playing_position);
        video.currentTime = np.now_playing_position;
      }
    }

    setTimeout(() => {
      if (!isMediaPlaying(video) && !video.paused) {
        endSong("failed to start");
      }
    }, playbackStartTimeout);
  }
}

async function loadNowPlaying() {
  const data = await $.get("/now_playing");
  handleNowPlayingUpdate(JSON.parse(data));
}

const setupOverlayMenus = () => {
  if (PikaraokeConfig.hideOverlay) {
    $('#bottom-container').hide();
    $('#top-container').hide();
  }
  $("#menu a").fadeOut(); // start hidden
  const triggerInactivity = () => {
    mouseTimer = null;
    document.body.style.cursor = 'none';
    cursorVisible = false;
    $("#menu a").fadeOut();
    if (PikaraokeConfig.showSplashClock) {
      setTimeout(() => {
        if (!cursorVisible) $("#clock").fadeIn();
      }, 1000);
    }
    menuButtonVisible = false;
  };

  document.onmousemove = function () {
    if (mouseTimer) window.clearTimeout(mouseTimer);
    if (!cursorVisible) {
      document.body.style.cursor = 'default';
      cursorVisible = true;
    }
    if (!menuButtonVisible) {
      $("#menu a").fadeIn();
      $("#clock").hide();
      menuButtonVisible = true;
    }
    mouseTimer = window.setTimeout(triggerInactivity, 5000);
  };

  // Set initial state to hidden
  triggerInactivity();
  $('#menu a').click(function (e) {
    e.preventDefault();
    e.stopPropagation();
    if (showMenu) {
      $('#menu-container').hide();
      $('#menu-container iframe').attr('src', '');
      showMenu = false;
    } else {
      setUserCookie();
      $("#menu-container").show();
      $("#menu-container iframe").attr("src", "/");
      showMenu = true;
    }
  });
  $('#menu-background').click(function () {
    if (showMenu) {
      $(".navbar-burger").click();
    }
  });
}

const setupVideoPlayer = () => {
  $('#video-container').hide();
  const video = getVideoPlayer();
  video.addEventListener("play", () => {
    $("#video-container").show();
    if (isMaster) {
      setTimeout(() => { socket.emit("start_song") }, 1200);
    }
  });

  // Master reports playback position to server
  setInterval(() => {
    if (isMaster && isMediaPlaying(video)) {
      socket.emit("playback_position", video.currentTime);
    }
  }, 1000);

  video.addEventListener("ended", () => { endSong("complete", true); });
  video.addEventListener("timeupdate", (e) => { $("#current").text(formatTime(video.currentTime)); });
  $("#video source")[0].addEventListener("error", (e) => {
    if (isMediaPlaying(video)) {
      endSong("error while playing");
    }
  });
  window.addEventListener(
    'beforeunload',
    function (event) {
      if (isMediaPlaying(video)) {
        endSong("splash screen closed");
      }
    },
    true
  );
}

const handleUnsupportedBrowser = () => {
  if (!isSupportedBrowser) {
    let modalContents = document.getElementById("permissions-modal-content");
    let warningMessage = document.createElement("p");
    warningMessage.classList.add("notification", "is-warning");
    warningMessage.innerHTML =
      PikaraokeConfig.translations.unsupportedBrowser;
    modalContents.prepend(warningMessage);
  }
}

const startClock = () => {
  if (clockIntervalId) return;
  const update = () => {
    const el = document.getElementById('clock');
    if (el) el.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: true });
  };
  update();
  clockIntervalId = setInterval(update, 1000);
}

const stopClock = () => {
  if (!clockIntervalId) return;
  clearInterval(clockIntervalId);
  clockIntervalId = null;
}

const PREFERENCE_EFFECTS = {
  show_splash_clock:   (v) => {
    PikaraokeConfig.showSplashClock = v;
    v ? startClock() : (stopClock(), $("#clock").hide());
  },
  hide_overlay:        (v) => {
    PikaraokeConfig.hideOverlay = v;
    $("#bottom-container, #top-container").toggle(!v);
  },
  hide_url:            (v) => { $("#qr-code").toggle(!v); },
  subtitle_delay:      (v) => {
    PikaraokeConfig.subtitleDelay = v;
    // Re-initialize subtitles with new offset if currently playing
    if (octopusInstance && nowPlaying.now_playing_subtitle_url) {
      octopusInstance.dispose();
      octopusInstance = null;
      const video = getVideoPlayer();
      const options = {
        video: video,
        subUrl: nowPlaying.now_playing_subtitle_url,
        fonts: ["/static/fonts/Arial.ttf", "/static/fonts/DroidSansFallback.ttf"],
        debug: true,
        workerUrl: "/static/js/subtitles-octopus-worker.js",
        timeOffset: PikaraokeConfig.subtitleDelay ? -PikaraokeConfig.subtitleDelay : 0
      };
      try {
        octopusInstance = new SubtitlesOctopus(options);
      } catch (e) { console.error(e); }
    }
  },
};

const parsePreferenceValue = (value) => {
  if (typeof value !== "string") return value;
  if (value === "True") return true;
  if (value === "False") return false;
  const num = Number(value);
  return !isNaN(num) && value.trim() !== "" ? num : value;
};

const applyPreferenceUpdate = (data) => {
  const effect = PREFERENCE_EFFECTS[data.key];
  if (effect) effect(parsePreferenceValue(data.value));
};

const applyPreferencesReset = (defaults) => {
  Object.entries(defaults).forEach(([key, value]) => applyPreferenceUpdate({ key, value }));
};

const setupSocketEvents = () => {
  socket.on('connect', () => {
    console.log('Socket connected');
    socket.emit("register_splash");
  });
  socket.on('splash_role', (role) => {
    isMaster = (role === "master");
    console.log("Splash role assigned:", role, isMaster ? "(Master active)" : "(Slave active - read-only)");
  });
  socket.on('connect_error', (error) => {
    console.error('Connection error:', error);
    flashNotification(PikaraokeConfig.translations.socketConnectionLost, "is-danger");
  });
  socket.on('disconnect', (reason) => {
    console.warn('Socket disconnected:', reason);
    flashNotification(PikaraokeConfig.translations.socketConnectionLost, "is-danger");
  });
  socket.on('pause', () => {
    const video = getVideoPlayer();
    const currVolume = video.volume;
    if (!video.paused) {
      $(video).animate({ volume: 0 }, 1000, () => {
        video.pause();
        video.volume = currVolume;
      });
    }
  });
  socket.on('play', () => {
    const video = getVideoPlayer();
    const currVolume = video.volume;
    if (video.paused) {
      video.play();
      video.volume = 0;
      $(video).animate({ volume: currVolume }, 1000);
    }
  });
  socket.on('skip', (reason) => {
    const video = getVideoPlayer();
    const currVolume = video.volume;
    if (isMediaPlaying(video)) {
      $(video).animate({ volume: 0 }, 1000, () => {
        video.pause();
        video.volume = currVolume;
        hideVideo();
      });
    } else {
      video.pause();
      hideVideo();
    }
  });
  socket.on('volume', (val) => {
    const video = getVideoPlayer();
    if (val === "up") {
      video.volume = Math.min(1, video.volume + 0.1);
    } else if (val === "down") {
      video.volume = Math.max(0, video.volume - 0.1);
    } else {
      video.volume = val;
    }
  });
  socket.on('restart', () => {
    const video = getVideoPlayer();
    video.currentTime = 0;
    if (video.paused) video.play();
  });
  socket.on("notification", (data) => {
    const notification = data.split("::");
    const message = notification[0];
    const categoryClass = notification.length > 1 ? notification[1] : "is-primary";
    flashNotification(message, categoryClass);
    if (isMaster) {
      socket.emit("clear_notification");
    }
  });
  socket.on("now_playing", handleNowPlayingUpdate);
  socket.on("preferences_update", applyPreferenceUpdate);
  socket.on("preferences_reset", applyPreferencesReset);
  socket.on("subtitle_delay", (delay) => {
    // Update subtitle delay when changed from home page (temporary for current song)
    if (nowPlaying) {
      nowPlaying.subtitle_delay = parseFloat(delay);
    }
    // Re-initialize subtitles if active to apply the new delay immediately
    if (octopusInstance && nowPlaying.now_playing_subtitle_url) {
      octopusInstance.dispose();
      octopusInstance = null;
      const video = getVideoPlayer();
      const delayValue = parseFloat(delay);
      const options = {
        video: video,
        subUrl: nowPlaying.now_playing_subtitle_url,
        fonts: ["/static/fonts/Arial.ttf", "/static/fonts/DroidSansFallback.ttf"],
        debug: true,
        workerUrl: "/static/js/subtitles-octopus-worker.js",
        // Invert the sign: user expects negative = earlier, but timeOffset works opposite
        timeOffset: delayValue ? -delayValue : 0
      };
      try {
        octopusInstance = new SubtitlesOctopus(options);
      } catch (e) { console.error(e); }
    }
  });

  socket.on("playback_position", (position) => {
    if (!isMaster) {
      const video = getVideoPlayer();
      if (isMediaPlaying(video)) {
        if (Math.abs(video.currentTime - position) > 2) {
          console.log("Slave drifting, syncing position to:", position);
          video.currentTime = position;
        }
      }
    }
  });
}

const handleSocketRecovery = () => {
  // A socket may disconnect if the tab is backgrounded for a while
  // Reconnect and configure event listeners when tab becomes visible again
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === 'visible') {
      autoplayConfirmed && loadNowPlaying();
      if (!socket.connected) {
        socket = io();
        setupSocketEvents();
      }
    }
  });
}

const setupUIScaling = () => {
  const urlParams = new URLSearchParams(window.location.search);
  const rawScale = urlParams.get('scale');
  if (!rawScale) return;
  uiScale = parseFloat(rawScale) || 1;

  const scaleTargets = [
    { selector: '#logo-container img.logo', origin: null },
    { selector: '#top-container', origin: 'top right' },
    { selector: '#ap-container', origin: 'top left' },
    { selector: '#qr-code', origin: 'bottom left' },
    { selector: '#up-next', origin: 'bottom right' },
    { selector: '#dvd', origin: null },
    { selector: '#splash-notification', origin: 'top left' },
    { selector: '#clock', origin: 'top left' },
  ];

  scaleTargets.forEach(({ selector, origin }) => {
    const el = document.querySelector(selector);
    if (el) {
      el.style.transform = `scale(${uiScale})`;
      if (origin) el.style.transformOrigin = origin;
    }
  });
}

// Document ready procedures

$(function () {
  // Setup various features and listeners
  setupUIScaling();
  if (PikaraokeConfig.showSplashClock) startClock();
  setupOverlayMenus();
  setupVideoPlayer();

  // Handle browser compatibility
  handleUnsupportedBrowser();
  testAutoplayCapability();
});


// Setup sockets and recovery outside of document ready to prevent race conditions
setupSocketEvents();
handleSocketRecovery();

// Fallback: if socket connected before listeners were attached, register now
if (socket.connected) {
  console.log('Socket already connected, registering splash...');
  socket.emit("register_splash");
}
