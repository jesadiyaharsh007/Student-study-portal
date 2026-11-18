/**
 * StudyPortal Watch Player
 * A dedicated, headless YouTube player with custom glassmorphism controls.
 * Eliminates all external watermarks, recommendations, and popups.
 */
(() => {
  'use strict';

  const player = document.getElementById('watchPlayer');
  if (!player) return;

  const iframe = document.getElementById('watchIframe');
  const ui = document.getElementById('watchUi');
  const pauseCover = document.getElementById('watchPauseCover');
  const spinner = document.getElementById('watchSpinner');
  const bigPlay = document.getElementById('watchBigPlay');
  const errScreen = document.getElementById('watchErrScreen');
  const uiBody = document.getElementById('watchUiBody');

  // Controls
  const btnPlay = document.getElementById('watchBtnPlay');
  const btnBack10 = document.getElementById('watchBtnBack10');
  const btnFwd10 = document.getElementById('watchBtnFwd10');
  const btnMute = document.getElementById('watchBtnMute');
  const volSlider = document.getElementById('watchVolSlider');
  const timeDisplay = document.getElementById('watchTime');

  // Seekbar
  const seekRail = document.getElementById('watchSeek');
  const seekBuf = document.getElementById('watchSeekBuf');
  const seekPlay = document.getElementById('watchSeekPlay');
  const seekThumb = document.getElementById('watchSeekThumb');
  const seekTip = document.getElementById('watchSeekTip');

  // Menus
  const btnQuality = document.getElementById('watchBtnQuality');
  const qualityMenu = document.getElementById('watchQualityMenu');
  const qualityLabel = document.getElementById('watchQualityLabel');

  const btnSpeed = document.getElementById('watchBtnSpeed');
  const speedMenu = document.getElementById('watchSpeedMenu');
  const speedLabel = document.getElementById('watchSpeedLabel');

  const btnFs = document.getElementById('watchBtnFs');

  // SVG Icons
  const ICON_PLAY = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5.14v13.72a1 1 0 0 0 1.52.85l11.1-6.86a1 1 0 0 0 0-1.7L9.52 4.29A1 1 0 0 0 8 5.14z" fill="currentColor"/></svg>';
  const ICON_PAUSE = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 4.5h3.2a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1v-13a1 1 0 0 1 1-1zm6.8 0H17a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-3.2a1 1 0 0 1-1-1v-13a1 1 0 0 1 1-1z" fill="currentColor"/></svg>';
  const ICON_VOL_HIGH = '<svg viewBox="0 0 24 24"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z" fill="currentColor"/></svg>';
  const ICON_VOL_LOW = '<svg viewBox="0 0 24 24"><path d="M18.5 12c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM5 9v6h4l5 5V4L9 9H5z" fill="currentColor"/></svg>';
  const ICON_VOL_MUTE = '<svg viewBox="0 0 24 24"><path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z" fill="currentColor"/></svg>';
  const ICON_FS_ENTER = '<svg viewBox="0 0 24 24"><path d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z" fill="currentColor"/></svg>';
  const ICON_FS_EXIT = '<svg viewBox="0 0 24 24"><path d="M5 16h3v3h2v-5H5v2zm3-8H5v2h5V5H8v3zm6 11h2v-3h3v-2h-5v5zm2-11V5h-2v5h5V8h-3z" fill="currentColor"/></svg>';

  // State
  let isPlaying = false;
  let duration = 0;
  let currentTime = 0;
  let volume = 100;
  let isMuted = false;
  let currentSpeed = 1;
  let currentQuality = 'auto';
  let isScrubbing = false;
  let hideUiTimeout = null;
  let tickerInterval = null;

  // Restore saved preferences
  try {
    const savedVol = localStorage.getItem('portal_player_vol');
    if (savedVol !== null) volume = Math.max(0, Math.min(100, parseInt(savedVol, 10)));
    const savedMuted = localStorage.getItem('portal_player_muted');
    if (savedMuted === '1') isMuted = true;
    const savedSpeed = localStorage.getItem('portal_player_speed');
    if (savedSpeed !== null) currentSpeed = parseFloat(savedSpeed) || 1;
  } catch (e) {}

  // PostMessage command dispatcher to the YouTube iframe
  function postCmd(func, args = []) {
    if (!iframe || !iframe.contentWindow) return;
    try {
      iframe.contentWindow.postMessage(JSON.stringify({
        event: 'command',
        func: func,
        args: args
      }), '*');
    } catch (e) {}
  }

  // Format seconds to H:MM:SS or M:SS
  function formatTime(s) {
    s = Math.max(0, Math.floor(s || 0));
    const h = Math.floor(s / 3600);
    const m = Math.floor(s / 60) % 60;
    const sec = s % 60;
    const secStr = String(sec).padStart(2, '0');
    if (h > 0) {
      return `${h}:${String(m).padStart(2, '0')}:${secStr}`;
    }
    return `${m}:${secStr}`;
  }

  // Paint seekbar and time display
  function paintProgress() {
    if (duration <= 0) {
      timeDisplay.textContent = `${formatTime(currentTime)} / 0:00`;
      return;
    }
    const ratio = Math.min(1, Math.max(0, currentTime / duration));
    const pct = (ratio * 100).toFixed(2) + '%';
    seekPlay.style.width = pct;
    seekThumb.style.left = pct;
    seekRail.setAttribute('aria-valuenow', String(Math.round(ratio * 100)));
    timeDisplay.textContent = `${formatTime(currentTime)} / ${formatTime(duration)}`;
  }

  // Paint volume slider and icon
  function paintVolume() {
    volSlider.value = isMuted ? 0 : volume;
    volSlider.style.setProperty('--vol-pct', `${isMuted ? 0 : volume}%`);
    if (isMuted || volume === 0) {
      btnMute.innerHTML = ICON_VOL_MUTE;
      btnMute.title = 'Unmute (M)';
    } else if (volume < 50) {
      btnMute.innerHTML = ICON_VOL_LOW;
      btnMute.title = 'Mute (M)';
    } else {
      btnMute.innerHTML = ICON_VOL_HIGH;
      btnMute.title = 'Mute (M)';
    }
  }

  // Toggle Play / Pause
  function togglePlay() {
    if (isPlaying) {
      postCmd('pauseVideo');
      setPlayState(false);
    } else {
      postCmd('playVideo');
      setPlayState(true);
    }
    pokeUi();
  }

  function setPlayState(playing) {
    isPlaying = playing;
    player.dataset.state = playing ? 'playing' : 'paused';
    btnPlay.innerHTML = playing ? ICON_PAUSE : ICON_PLAY;
    btnPlay.setAttribute('aria-label', playing ? 'Pause' : 'Play');
    btnPlay.title = playing ? 'Pause (Space)' : 'Play (Space)';

    if (playing) {
      spinner.hidden = true;
      startTicker();
      scheduleHideUi();
    } else {
      stopTicker();
      cancelHideUi();
    }
  }

  function seekTo(sec) {
    sec = Math.max(0, Math.min(duration || sec, sec));
    currentTime = sec;
    postCmd('seekTo', [sec, true]);
    paintProgress();
    pokeUi();
  }

  function setVol(newVol) {
    volume = Math.max(0, Math.min(100, Math.round(newVol)));
    isMuted = (volume === 0);
    postCmd('setVolume', [volume]);
    if (isMuted) postCmd('mute'); else postCmd('unMute');
    paintVolume();
    try {
      localStorage.setItem('portal_player_vol', String(volume));
      localStorage.setItem('portal_player_muted', isMuted ? '1' : '0');
    } catch (e) {}
    pokeUi();
  }

  function toggleMute() {
    isMuted = !isMuted;
    if (isMuted) {
      postCmd('mute');
    } else {
      postCmd('unMute');
      if (volume === 0) volume = 60;
      postCmd('setVolume', [volume]);
    }
    paintVolume();
    try {
      localStorage.setItem('portal_player_muted', isMuted ? '1' : '0');
    } catch (e) {}
    pokeUi();
  }

  function setSpeed(rate) {
    currentSpeed = rate;
    postCmd('setPlaybackRate', [rate]);
    speedLabel.textContent = rate === 1 ? '1x' : `${rate}x`;
    speedMenu.querySelectorAll('.watch-opt').forEach(b => {
      b.classList.toggle('active', parseFloat(b.dataset.speed) === rate);
    });
    speedMenu.hidden = true;
    try {
      localStorage.setItem('portal_player_speed', String(rate));
    } catch (e) {}
    pokeUi();
  }

  function setQuality(q) {
    currentQuality = q;
    const ytQ = q === 'auto' ? 'default' : (q >= 720 ? `hd${q}` : (q === '480' ? 'large' : 'medium'));
    postCmd('setPlaybackQuality', [ytQ]);
    postCmd('setPlaybackQualityRange', [ytQ, ytQ]);
    qualityLabel.textContent = q === 'auto' ? 'Auto' : `${q}p`;
    btnQuality.classList.toggle('hd', q === '1080' || q === '720');
    qualityMenu.querySelectorAll('.watch-opt').forEach(b => {
      b.classList.toggle('active', b.dataset.q === q);
    });
    qualityMenu.hidden = true;
    pokeUi();
  }

  // Fullscreen toggle
  function toggleFullscreen() {
    if (!document.fullscreenElement) {
      if (player.requestFullscreen) {
        player.requestFullscreen().catch(() => {});
      } else if (player.webkitRequestFullscreen) {
        player.webkitRequestFullscreen();
      }
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen().catch(() => {});
      }
    }
  }

  document.addEventListener('fullscreenchange', () => {
    const isFs = !!document.fullscreenElement;
    player.classList.toggle('is-fullscreen', isFs);
    btnFs.innerHTML = isFs ? ICON_FS_EXIT : ICON_FS_ENTER;
    btnFs.title = isFs ? 'Exit full screen (F)' : 'Full screen (F)';
  });

  // UI auto-hide management
  function pokeUi() {
    player.classList.add('show-ui');
    scheduleHideUi();
  }

  function scheduleHideUi() {
    cancelHideUi();
    if (isPlaying && !isScrubbing && qualityMenu.hidden && speedMenu.hidden) {
      hideUiTimeout = setTimeout(() => {
        if (isPlaying && !isScrubbing) {
          player.classList.remove('show-ui');
        }
      }, 2500);
    }
  }

  function cancelHideUi() {
    if (hideUiTimeout) {
      clearTimeout(hideUiTimeout);
      hideUiTimeout = null;
    }
  }

  // Smooth ticker for scrubber when playing
  function startTicker() {
    stopTicker();
    tickerInterval = setInterval(() => {
      if (!isScrubbing && isPlaying) {
        currentTime += 0.25;
        if (duration > 0 && currentTime > duration) currentTime = duration;
        paintProgress();
      }
    }, 250);
  }

  function stopTicker() {
    if (tickerInterval) {
      clearInterval(tickerInterval);
      tickerInterval = null;
    }
  }

  // Handle YouTube iframe PostMessage events
  window.addEventListener('message', ev => {
    let data = ev.data;
    if (typeof data === 'string') {
      try { data = JSON.parse(data); } catch (e) { return; }
    }
    if (!data) return;

    // infoDelivery
    if (data.event === 'infoDelivery' && data.info) {
      const info = data.info;
      if (typeof info.duration === 'number' && info.duration > 0) {
        duration = info.duration;
      }
      if (typeof info.currentTime === 'number' && !isScrubbing) {
        currentTime = info.currentTime;
      }
      if (typeof info.videoLoadedFraction === 'number' && duration > 0) {
        seekBuf.style.width = `${(info.videoLoadedFraction * 100).toFixed(1)}%`;
      }
      if (info.playbackQuality && currentQuality === 'auto') {
        const h = info.playbackQuality.replace(/^hd/, '');
        if (h === '1080' || h === '720') {
          qualityLabel.textContent = `${h}p`;
          btnQuality.classList.add('hd');
        }
      }
      if (typeof info.playerState === 'number') {
        handlePlayerState(info.playerState);
      }
      paintProgress();
    }

    // onStateChange
    if (data.event === 'onStateChange' && typeof data.info === 'number') {
      handlePlayerState(data.info);
    }

    // onError
    if (data.event === 'onError') {
      const code = data.info;
      if (code === 101 || code === 150 || code === 153) {
        errScreen.hidden = false;
        player.dataset.state = 'error';
      }
    }
  });

  function handlePlayerState(s) {
    if (s === 1) { // Playing
      setPlayState(true);
      spinner.hidden = true;
    } else if (s === 2) { // Paused
      setPlayState(false);
      spinner.hidden = true;
    } else if (s === 3) { // Buffering
      player.dataset.state = 'buffering';
      spinner.hidden = false;
    } else if (s === 0) { // Ended
      setPlayState(false);
      currentTime = duration;
      paintProgress();
      player.dataset.state = 'ended';
    }
  }

  // Initialize iframe connection on load
  function initIframeHandshake() {
    postCmd('listening');
    if (currentSpeed !== 1) postCmd('setPlaybackRate', [currentSpeed]);
    postCmd('setVolume', [isMuted ? 0 : volume]);
    if (isMuted) postCmd('mute'); else postCmd('unMute');
    paintVolume();
  }

  iframe.addEventListener('load', () => {
    setTimeout(initIframeHandshake, 300);
    setTimeout(initIframeHandshake, 1200);
  });

  // Scrub bar interaction
  function getScrubFraction(e) {
    const rect = seekRail.getBoundingClientRect();
    const x = e.clientX - rect.left;
    return Math.max(0, Math.min(1, x / rect.width));
  }

  seekRail.addEventListener('pointerdown', e => {
    isScrubbing = true;
    seekRail.setPointerCapture(e.pointerId);
    const frac = getScrubFraction(e);
    currentTime = frac * (duration || 0);
    paintProgress();
    pokeUi();
  });

  seekRail.addEventListener('pointermove', e => {
    const frac = getScrubFraction(e);
    const tipTime = frac * (duration || 0);
    seekTip.textContent = formatTime(tipTime);
    seekTip.style.left = `${(frac * 100).toFixed(2)}%`;
    if (isScrubbing) {
      currentTime = tipTime;
      paintProgress();
    }
  });

  function endScrub(e) {
    if (!isScrubbing) return;
    isScrubbing = false;
    const frac = getScrubFraction(e);
    seekTo(frac * (duration || 0));
  }

  seekRail.addEventListener('pointerup', endScrub);
  seekRail.addEventListener('pointercancel', endScrub);

  // Volume slider interaction
  volSlider.addEventListener('input', () => {
    setVol(parseInt(volSlider.value, 10));
  });

  // Button clicks
  btnPlay.addEventListener('click', togglePlay);
  bigPlay.addEventListener('click', togglePlay);
  btnBack10.addEventListener('click', () => seekTo(currentTime - 10));
  btnFwd10.addEventListener('click', () => seekTo(currentTime + 10));
  btnMute.addEventListener('click', toggleMute);
  btnFs.addEventListener('click', toggleFullscreen);

  // Click on video area to toggle play/pause
  uiBody.addEventListener('click', e => {
    if (e.target === uiBody) togglePlay();
  });

  // Quality & Speed menu toggles
  btnQuality.addEventListener('click', e => {
    e.stopPropagation();
    qualityMenu.hidden = !qualityMenu.hidden;
    speedMenu.hidden = true;
    pokeUi();
  });

  btnSpeed.addEventListener('click', e => {
    e.stopPropagation();
    speedMenu.hidden = !speedMenu.hidden;
    qualityMenu.hidden = true;
    pokeUi();
  });

  qualityMenu.addEventListener('click', e => {
    const b = e.target.closest('.watch-opt');
    if (!b) return;
    setQuality(b.dataset.q);
  });

  speedMenu.addEventListener('click', e => {
    const b = e.target.closest('.watch-opt');
    if (!b) return;
    setSpeed(parseFloat(b.dataset.speed));
  });

  document.addEventListener('click', e => {
    if (!qualityMenu.hidden && !qualityMenu.contains(e.target) && e.target !== btnQuality) {
      qualityMenu.hidden = true;
    }
    if (!speedMenu.hidden && !speedMenu.contains(e.target) && e.target !== btnSpeed) {
      speedMenu.hidden = true;
    }
  });

  // UI mouse/pointer activity tracker
  player.addEventListener('pointermove', pokeUi);
  player.addEventListener('pointerdown', pokeUi);
  player.addEventListener('mouseleave', () => {
    if (isPlaying) player.classList.remove('show-ui');
  });

  // Keyboard navigation
  window.addEventListener('keydown', e => {
    const active = document.activeElement;
    if (active && (/^(INPUT|TEXTAREA|SELECT)$/.test(active.tagName) || active.isContentEditable)) {
      if (active !== volSlider && active !== seekRail) return;
    }

    const key = e.key;
    if (key === ' ' || key === 'k' || key === 'K') {
      e.preventDefault();
      togglePlay();
    } else if (key === 'ArrowLeft') {
      e.preventDefault();
      seekTo(currentTime - 5);
    } else if (key === 'ArrowRight') {
      e.preventDefault();
      seekTo(currentTime + 5);
    } else if (key === 'j' || key === 'J') {
      e.preventDefault();
      seekTo(currentTime - 10);
    } else if (key === 'l' || key === 'L') {
      e.preventDefault();
      seekTo(currentTime + 10);
    } else if (key === 'ArrowUp') {
      e.preventDefault();
      setVol(volume + 5);
    } else if (key === 'ArrowDown') {
      e.preventDefault();
      setVol(volume - 5);
    } else if (key === 'm' || key === 'M') {
      e.preventDefault();
      toggleMute();
    } else if (key === 'f' || key === 'F') {
      e.preventDefault();
      toggleFullscreen();
    } else if (/^[0-9]$/.test(key)) {
      if (duration > 0) {
        e.preventDefault();
        seekTo(duration * (parseInt(key, 10) / 10));
      }
    }
  });

  // Initial setup
  btnPlay.innerHTML = ICON_PLAY;
  btnFs.innerHTML = ICON_FS_ENTER;
  paintVolume();
  paintProgress();
})();
