/*
 * Shared browser Text-to-Speech (Web Speech API) helper for accessibility.
 * Any page can add a button with class "tts-btn" and data-tts-target="<id>"
 * (reads that element's textContent), data-tts-text="literal string", or
 * data-tts-text-fn="globalFunctionName" (computed narration), and this
 * module wires click-to-speak/click-to-stop automatically.
 *
 * Reliability notes: getVoices() returns an empty list on many browsers
 * until the async 'voiceschanged' event fires at least once, so a naive
 * "speak on first click" implementation silently falls back to whatever
 * default voice the OS picks (often the wrong language). This module caches
 * the voice list once loaded and, if a speak() call arrives before voices
 * are ready, waits briefly for them rather than guessing.
 */
window.JointXTTS = (function () {
  const LANG_TAGS = {
    en: 'en-IN', hi: 'hi-IN', bn: 'bn-IN', as: 'as-IN', brx: 'hi-IN', mni: 'hi-IN',
    kha: 'en-IN', grt: 'en-IN', lus: 'en-IN', nag: 'en-IN', ne: 'ne-NP', kok: 'bn-IN', ta: 'ta-IN',
  };

  let activeBtn = null;
  let cachedVoices = [];

  function supported() {
    return 'speechSynthesis' in window;
  }

  function refreshVoiceCache() {
    if (!supported()) return;
    const list = speechSynthesis.getVoices();
    if (list && list.length) cachedVoices = list;
  }

  function waitForVoices(timeoutMs) {
    refreshVoiceCache();
    if (cachedVoices.length) return Promise.resolve(cachedVoices);
    return new Promise((resolve) => {
      let settled = false;
      const done = () => {
        if (settled) return;
        settled = true;
        refreshVoiceCache();
        resolve(cachedVoices);
      };
      if (supported()) speechSynthesis.onvoiceschanged = done;
      setTimeout(done, timeoutMs || 400);
    });
  }

  function currentLangTag() {
    const lang = (window.JointXI18n && window.JointXI18n.currentLang) || 'en';
    return LANG_TAGS[lang] || 'en-IN';
  }

  function bestVoiceFor(langTag) {
    const target = langTag.toLowerCase();
    return cachedVoices.find((v) => (v.lang || '').toLowerCase() === target)
      || cachedVoices.find((v) => (v.lang || '').toLowerCase().startsWith(target.split('-')[0]));
  }

  function stop() {
    if (supported()) speechSynthesis.cancel();
    if (activeBtn) activeBtn.classList.remove('is-speaking');
    activeBtn = null;
  }

  async function speak(text, btn) {
    if (!supported()) {
      alert('Speech playback is not supported by this browser.');
      return;
    }
    const clean = (text || '').replace(/\s+/g, ' ').trim();
    if (activeBtn === btn && speechSynthesis.speaking) {
      stop();
      return;
    }
    stop();
    if (!clean) return;

    await waitForVoices();

    const utter = new SpeechSynthesisUtterance(clean);
    const langTag = currentLangTag();
    utter.lang = langTag;
    utter.rate = 0.95;
    const voice = bestVoiceFor(langTag);
    if (voice) {
      utter.voice = voice;
    } else {
      // No installed voice for this exact language — Chrome/Edge/Safari
      // still attempt best-effort pronunciation from utter.lang alone, but
      // make this visible rather than silently mispronouncing content.
      console.warn(`JointXTTS: no installed voice found for "${langTag}"; using the browser's default voice.`);
    }
    utter.onstart = () => { activeBtn = btn; if (btn) btn.classList.add('is-speaking'); };
    utter.onend = () => { if (activeBtn === btn) activeBtn = null; if (btn) btn.classList.remove('is-speaking'); };
    utter.onerror = () => { if (activeBtn === btn) activeBtn = null; if (btn) btn.classList.remove('is-speaking'); };
    speechSynthesis.speak(utter);
  }

  function initButtons() {
    document.querySelectorAll('.tts-btn').forEach((btn) => {
      if (btn.dataset.jxttsBound) return;
      btn.dataset.jxttsBound = '1';
      btn.addEventListener('click', () => {
        let text;
        if (btn.dataset.ttsTextFn && typeof window[btn.dataset.ttsTextFn] === 'function') {
          text = window[btn.dataset.ttsTextFn]();
        } else if (btn.hasAttribute('data-tts-text')) {
          text = btn.getAttribute('data-tts-text');
        } else {
          const targetId = btn.getAttribute('data-tts-target');
          const el = targetId && document.getElementById(targetId);
          text = el ? el.textContent : '';
        }
        speak(text, btn);
      });
    });
  }

  if (supported()) {
    refreshVoiceCache();
    speechSynthesis.onvoiceschanged = refreshVoiceCache;
  }
  document.addEventListener('DOMContentLoaded', initButtons);

  return { speak, stop, initButtons, supported };
})();
