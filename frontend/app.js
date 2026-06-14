

class VeauidoApp {
  /** @type {HTMLFormElement} */       form;
  /** @type {HTMLInputElement} */      urlInput;
  /** @type {HTMLButtonElement} */     submitBtn;
  /** @type {HTMLButtonElement} */     clearBtn;
  /** @type {HTMLVideoElement} */      video;
  /** @type {HTMLElement} */           captionOverlay;
  /** @type {HTMLElement} */           captionOverlayText;
  /** @type {HTMLUListElement} */      timeline;
  /** @type {Array<Object>} */        captions = [];
  /** @type {number} */               activeCaptionIdx = -1;
  /** @type {string|null} */          currentVideoId = null;

  static STORAGE_KEY = 'veauido_history';
  static MAX_HISTORY = 8;
  static STEPS = ['downloading', 'detecting', 'captioning', 'complete'];

  constructor() {
    this.cacheDOM();
    this.bindEvents();
    this.renderHistory();
    this.loadSiteUrl();
  }

  async loadSiteUrl() {
    try {
      const response = await fetch('/api/site');
      if (!response.ok) return;
      const site = await response.json();
      const canonical = document.getElementById('canonicalLink');
      if (canonical && site.public_url) {
        canonical.href = site.public_url;
      }
    } catch {
    
    }
  }


  cacheDOM() {
    this.form               = document.getElementById('captionForm');
    this.urlInput            = document.getElementById('videoUrlInput');
    this.submitBtn           = document.getElementById('submitBtn');
    this.clearBtn            = document.getElementById('clearInputBtn');

    this.statusSection       = document.getElementById('statusSection');
    this.errorSection        = document.getElementById('errorSection');
    this.errorMessage        = document.getElementById('errorMessage');
    this.errorDismissBtn     = document.getElementById('errorDismissBtn');

    this.resultsSection      = document.getElementById('resultsSection');
    this.video               = document.getElementById('videoPlayer');
    this.captionOverlay      = document.getElementById('captionOverlay');
    this.captionOverlayText  = document.getElementById('captionOverlayText');

    this.metaDuration        = document.getElementById('metaDurationVal');
    this.metaCaptions        = document.getElementById('metaCaptionsVal');
    this.metaTime            = document.getElementById('metaTimeVal');

    this.timeline            = document.getElementById('captionTimeline');
    this.copyBtn             = document.getElementById('copyBtn');
    this.downloadSrtBtn      = document.getElementById('downloadSrtBtn');
    this.downloadJsonBtn     = document.getElementById('downloadJsonBtn');

    this.historySection      = document.getElementById('historySection');
    this.historyList          = document.getElementById('historyList');

    this.toast               = document.getElementById('toast');
    this.toastMessage        = document.getElementById('toastMessage');
  }

  
  bindEvents() {
    this.form.addEventListener('submit', (e) => { e.preventDefault(); this.handleSubmit(); });
    this.urlInput.addEventListener('input', () => this.onInputChange());
    this.urlInput.addEventListener('paste', () => setTimeout(() => this.onInputChange(), 0));
    this.clearBtn.addEventListener('click', () => this.clearInput());
    this.errorDismissBtn.addEventListener('click', () => this.hideError());

    this.video.addEventListener('timeupdate', () => this.syncCaptions());
    this.video.addEventListener('loadedmetadata', () => {
      this.metaDuration.textContent = this.formatTimestamp(this.video.duration);
    });

    this.copyBtn.addEventListener('click', () => this.copyAllCaptions());
    this.downloadSrtBtn.addEventListener('click', () => this.downloadSRT());
    this.downloadJsonBtn.addEventListener('click', () => this.downloadJSON());

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => this.handleKeyboard(e));
  }

  
  onInputChange() {
    const hasValue = this.urlInput.value.trim().length > 0;
    this.clearBtn.hidden = !hasValue;
  }

  clearInput() {
    this.urlInput.value = '';
    this.clearBtn.hidden = true;
    this.urlInput.focus();
  }

  async handleSubmit() {
    const url = this.urlInput.value.trim();
    if (!url) {
      this.showError('Please enter a video URL.');
      return;
    }

    try {
      new URL(url);
    } catch {
      this.showError('Please enter a valid URL.');
      return;
    }

    // Reset UI
    this.hideError();
    this.resultsSection.hidden = true;
    this.submitBtn.disabled = true;
    this.submitBtn.querySelector('span').textContent = 'Processing...';

    // Show status
    this.showProcessingStatus('downloading');

    try {
      // Simulate step progression for UX feedback
      const stepTimer1 = setTimeout(() => this.showProcessingStatus('detecting'), 3000);
      const stepTimer2 = setTimeout(() => this.showProcessingStatus('captioning'), 7000);

      const response = await fetch('/api/caption', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      });

      clearTimeout(stepTimer1);
      clearTimeout(stepTimer2);

      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(data.error || `Server error (${response.status})`);
      }

      // Mark complete
      this.showProcessingStatus('complete');
      await this.delay(600);

      // Hide status, show results
      this.statusSection.hidden = true;

      this.currentVideoId = data.video_id;
      this.captions = data.captions || [];

      this.displayVideo(data.video_serve_url);
      this.displayCaptions(this.captions);

      // Metadata
      this.metaDuration.textContent = this.formatTimestamp(data.duration || 0);
      this.metaCaptions.textContent = `${this.captions.length} caption${this.captions.length !== 1 ? 's' : ''}`;
      this.metaTime.textContent = `${(data.processing_time || 0).toFixed(1)}s`;

      this.resultsSection.hidden = false;

      
      setTimeout(() => {
        this.resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 100);

      
      this.saveToHistory(url, data);
      this.renderHistory();

    } catch (err) {
      this.statusSection.hidden = true;
      this.showError(err.message || 'Something went wrong. Please try again.');
    } finally {
      this.submitBtn.disabled = false;
      this.submitBtn.querySelector('span').textContent = 'Generate Captions';
    }
  }

  
  displayVideo(videoUrl) {
    this.video.src = videoUrl;
    this.video.load();
    this.activeCaptionIdx = -1;
    this.captionOverlay.classList.remove('visible');
    this.captionOverlayText.textContent = '';
  }

  displayCaptions(captions) {
    this.timeline.innerHTML = '';

    captions.forEach((cap, idx) => {
      const li = document.createElement('li');
      li.className = 'caption-item';
      li.style.animationDelay = `${idx * 0.05}s`;
      li.setAttribute('role', 'listitem');
      li.setAttribute('tabindex', '0');
      li.dataset.index = idx;

      li.innerHTML = `
        <span class="caption-timestamp">${this.formatTimestamp(cap.start)} - ${this.formatTimestamp(cap.end)}</span>
        <span class="caption-text">${this.escapeHtml(cap.text)}</span>
      `;

      li.addEventListener('click', () => this.seekToCaption(idx));
      li.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          this.seekToCaption(idx);
        }
      });

      this.timeline.appendChild(li);
    });
  }

  syncCaptions() {
    const t = this.video.currentTime;
    let found = -1;

    for (let i = 0; i < this.captions.length; i++) {
      if (t >= this.captions[i].start && t < this.captions[i].end) {
        found = i;
        break;
      }
    }

    if (found === this.activeCaptionIdx) return;
    this.activeCaptionIdx = found;

  
    if (found >= 0) {
      this.captionOverlayText.textContent = this.captions[found].text;
      this.captionOverlay.classList.add('visible');
    } else {
      this.captionOverlay.classList.remove('visible');
    }

    
    const items = this.timeline.querySelectorAll('.caption-item');
    items.forEach((item, idx) => {
      item.classList.toggle('active', idx === found);
    });

    
    if (found >= 0 && items[found]) {
      items[found].scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }

  seekToCaption(index) {
    if (index < 0 || index >= this.captions.length) return;
    this.video.currentTime = this.captions[index].start;
    if (this.video.paused) this.video.play();
  }

  
  copyAllCaptions() {
    if (!this.captions.length) return;

    const text = this.captions
      .map((c) => `[${this.formatTimestamp(c.start)} - ${this.formatTimestamp(c.end)}] ${c.text}`)
      .join('\n');

    navigator.clipboard.writeText(text).then(() => {
      this.showToast('Captions copied to clipboard');
    }).catch(() => {
      this.showToast('Failed to copy');
    });
  }

  downloadSRT() {
    if (!this.captions.length) return;

    const srt = this.captions.map((c, i) => {
      const start = this.formatSRTTime(c.start);
      const end   = this.formatSRTTime(c.end);
      return `${i + 1}\n${start} --> ${end}\n${c.text}\n`;
    }).join('\n');

    this.downloadFile(srt, `veauido-${this.currentVideoId || 'captions'}.srt`, 'text/srt');
    this.showToast('SRT file downloaded');
  }

  downloadJSON() {
    if (!this.captions.length) return;

    const json = JSON.stringify({
      video_id: this.currentVideoId,
      captions: this.captions,
      exported_at: new Date().toISOString(),
    }, null, 2);

    this.downloadFile(json, `veauido-${this.currentVideoId || 'captions'}.json`, 'application/json');
    this.showToast('JSON file downloaded');
  }

  downloadFile(content, filename, mimeType) {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  
  showProcessingStatus(currentStep) {
    this.statusSection.hidden = false;
    const stepIndex = VeauidoApp.STEPS.indexOf(currentStep);

    VeauidoApp.STEPS.forEach((step, idx) => {
      const el = document.getElementById(`step-${step}`);
      if (!el) return;

      el.classList.remove('pending', 'active', 'done');

      if (idx < stepIndex) {
        el.classList.add('done');
      } else if (idx === stepIndex) {
        el.classList.add('active');
      } else {
        el.classList.add('pending');
      }
    });
  }

  
  showError(message) {
    this.errorMessage.textContent = message;
    this.errorSection.hidden = false;
    this.errorSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  hideError() {
    this.errorSection.hidden = true;
  }

  
  showToast(message, duration = 2500) {
    this.toastMessage.textContent = message;
    this.toast.hidden = false;

    
    void this.toast.offsetHeight;
    this.toast.classList.add('show');

    clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => {
      this.toast.classList.remove('show');
      setTimeout(() => { this.toast.hidden = true; }, 300);
    }, duration);
  }

  
  getHistory() {
    try {
      return JSON.parse(localStorage.getItem(VeauidoApp.STORAGE_KEY)) || [];
    } catch {
      return [];
    }
  }

  saveToHistory(url, data) {
    const history = this.getHistory();
    const entry = {
      url,
      video_id: data.video_id,
      captionCount: (data.captions || []).length,
      duration: data.duration,
      date: new Date().toISOString(),
    };

   
    const filtered = history.filter((h) => h.url !== url);
    filtered.unshift(entry);

    localStorage.setItem(
      VeauidoApp.STORAGE_KEY,
      JSON.stringify(filtered.slice(0, VeauidoApp.MAX_HISTORY))
    );
  }

  renderHistory() {
    const history = this.getHistory();
    if (!history.length) {
      this.historySection.hidden = true;
      return;
    }

    this.historySection.hidden = false;
    this.historyList.innerHTML = '';

    history.forEach((entry) => {
      const li = document.createElement('li');
      li.className = 'history-item';
      li.setAttribute('tabindex', '0');

      const dateStr = new Date(entry.date).toLocaleDateString(undefined, {
        month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
      });

      li.innerHTML = `
        <span class="history-url" title="${this.escapeHtml(entry.url)}">${this.escapeHtml(entry.url)}</span>
        <span class="history-date">${dateStr}</span>
      `;

      li.addEventListener('click', () => {
        this.urlInput.value = entry.url;
        this.onInputChange();
        this.urlInput.focus();
        window.scrollTo({ top: 0, behavior: 'smooth' });
      });

      this.historyList.appendChild(li);
    });
  }

 
  handleKeyboard(e) {
    // Enter to submit (when input focused)
    if (e.key === 'Enter' && document.activeElement === this.urlInput) {
      return; // form handles it
    }

    
    if (e.key === ' ' && !['INPUT', 'TEXTAREA', 'BUTTON'].includes(document.activeElement.tagName)) {
      if (!this.resultsSection.hidden) {
        e.preventDefault();
        this.video.paused ? this.video.play() : this.video.pause();
      }
    }
  }


  formatTimestamp(seconds) {
    if (typeof seconds !== 'number' || isNaN(seconds)) return '0:00';
    const s = Math.max(0, seconds);
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = Math.floor(s % 60);

    if (h > 0) {
      return `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
    }
    return `${m}:${String(sec).padStart(2, '0')}`;
  }

  formatSRTTime(seconds) {
    const s = Math.max(0, seconds);
    const h   = Math.floor(s / 3600);
    const m   = Math.floor((s % 3600) / 60);
    const sec = Math.floor(s % 60);
    const ms  = Math.round((s % 1) * 1000);

    return [
      String(h).padStart(2, '0'),
      String(m).padStart(2, '0'),
      String(sec).padStart(2, '0'),
    ].join(':') + ',' + String(ms).padStart(3, '0');
  }


  escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  delay(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}


document.addEventListener('DOMContentLoaded', () => {
  window.veauido = new VeauidoApp();
});
