/*
 * Shared browser Text-to-Speech (Web Speech API) helper for accessibility.
 * Any page can add a button with class "tts-btn" and data-tts-target="<id>"
 * (reads that element's textContent) or data-tts-text="literal string", and
 * this module wires click-to-speak/click-to-stop automatically.
 */
window.JointXTTS = (function () {
  const LANG_TAGS = {
    en: 'en-IN', hi: 'hi-IN', bn: 'bn-IN', as: 'as-IN', brx: 'hi-IN', mni: 'hi-IN',
    kha: 'en-IN', grt: 'en-IN', lus: 'en-IN', nag: 'en-IN', ne: 'ne-NP', kok: 'bn-IN', ta: 'ta-IN',
  };

  let activeBtn = null;

  function supported() {
    return 'speechSynthesis' in window;
  }

  function currentLangTag() {
    const lang = (window.JointXI18n && window.JointXI18n.currentLang) || 'en';
    return LANG_TAGS[lang] || 'en-IN';
  }

  function bestVoiceFor(langTag) {
    const voices = speechSynthesis.getVoices();
    const target = langTag.toLowerCase();
    return voices.find((v) => (v.lang || '').toLowerCase() === target)
      || voices.find((v) => (v.lang || '').toLowerCase().startsWith(target.split('-')[0]));
  }

  function stop() {
    if (supported()) speechSynthesis.cancel();
    if (activeBtn) activeBtn.classList.remove('is-speaking');
    activeBtn = null;
  }

  function speak(text, btn) {
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
    const utter = new SpeechSynthesisUtterance(clean);
    const langTag = currentLangTag();
    utter.lang = langTag;
    utter.rate = 0.95;
    const voice = bestVoiceFor(langTag);
    if (voice) utter.voice = voice;
    utter.onstart = () => { activeBtn = btn; if (btn) btn.classList.add('is-speaking'); };
    utter.onend = () => { if (activeBtn === btn) activeBtn = null; if (btn) btn.classList.remove('is-speaking'); };
    utter.onerror = () => { if (activeBtn === btn) activeBtn = null; if (btn) btn.classList.remove('is-speaking'); };
    speechSynthesis.speak(utter);
  }

  function initButtons() {
    document.querySelectorAll('.tts-btn').forEach((btn) => {
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
    speechSynthesis.onvoiceschanged = () => {};
  }
  document.addEventListener('DOMContentLoaded', initButtons);

  return { speak, stop, initButtons, supported };
})();
