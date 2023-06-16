/**
 * Support explorer and command. Require ES8.
 */
document.addEventListener("DOMContentLoaded", function () {
  /* Explorer */
  explorer.init();

  /* Tools */
  document.getElementById("tools").addEventListener("change", onToolsChange, false);

  /* Command handler */
  document.getElementById("command").addEventListener("focus", onCommandFocus, false);
  document.getElementById("command").addEventListener("change", onCommandChange, false);
  document.getElementById('upload-file-selector').addEventListener('change', onUploadFileChange, false);
  document.getElementById('upload-dir-selector').addEventListener('change', onUploadDirChange, false);
  document.addEventListener("dragover", onDragOver, false);
  document.addEventListener("drop", onDrop, false);

  /* Show panel if init ok */
  document.getElementById("panel").hidden = false;
}, false);

const explorer = {
  init() {
    const mainElem = document.querySelector('main');

    /* Extend data table to support selection */
    document.querySelector('main').addEventListener("click", this.onMainClick, false);
    document.getElementById("explorer").addEventListener("change", this.onExplorerChange, false);

    const dir = mainElem.dataset.path;

    /* Auto view .htd (disable with any search or hash) */
    if (/\.(htd)\/?$/i.test(dir) && !/[?#]/.test(location)) {
      // if there's index.html, redirect to view it
      const indexAnchor = mainElem.querySelector('[data-entry] a[href="index.html"]');
      if (indexAnchor) {
        location.replace(indexAnchor.href);
        return;
      }

      // otherwise, preview the first entry
      previewer.toggle(true, {persist: false});
      previewer.preview(0);
      return;
    }

    const mode = sessionStorage.getItem('explorer') || localStorage.getItem('explorer') || 'default';
    this.switchView(mode, {persist: false});

    const preview = sessionStorage.getItem('previewer') || localStorage.getItem('previewer');
    previewer.toggle(!!preview, {persist: false});
  },

  async switchView(mode = null, {persist = true, syncTable = true} = {}) {
    const switcher = document.getElementById("explorer");
    if (mode === null) {
      mode = switcher.value;
    }

    if (syncTable) {
      this.syncTable();
    }
    switch (mode) {
      case "gallery":
        await this.switchViewGallery();
        break;
      case "gallery2":
        await this.switchViewGallery({loadMetadata: true});
        break;
      default:
        mode = 'table';
        await this.switchViewTable();
        break;
    }

    if (switcher.value !== mode) {
      switcher.value = mode;
    }

    if (persist) {
      sessionStorage.setItem('explorer', mode);
      localStorage.setItem('explorer', mode);
    }
  },

  switchViewTable() {
    const mainElem = document.querySelector('main');
    const dataTable = dataTableHandler.elem;

    if (mainElem.contains(dataTable)) { return; }

    mainElem.textContent = '';
    mainElem.appendChild(dataTable);
  },

  async switchViewGallery(options = {}) {
    const mainElem = document.querySelector('main');
    const dataTable = dataTableHandler.elem;

    const wrapper = document.createElement('div');
    wrapper.id = "img-gallery-view";

    const entries = await Promise.all(Array.prototype.map.call(dataTable.querySelectorAll('[data-entry]'), async (entry) => {
      const a = entry.querySelector('a[href]');
      if (a) { await this.loadAnchorMetadata(a); }
      return entry;
    }));

    const medias = [];
    for (const entry of entries) {
      const a = entry.querySelector('a[href]');
      if (!a) { continue; }

      const figure = wrapper.appendChild(document.createElement('figure'));
      figure.dataset.entry = '';
      figure.dataset.type = entry.dataset.type;
      figure.dataset.path = entry.dataset.path;
      figure.hidden = entry.hidden;
      this.highlight(figure, this.isHighlighted(entry), {updateSelectionHint: false});

      const div = figure.appendChild(document.createElement('div'));

      const type = a.dataset.type;
      const href = a.dataset.href || a.href;
      switch (type) {
        case 'image': {
          const img = div.appendChild(document.createElement('img'));
          img.src = href;
          img.alt = a.textContent;
          break;
        }
        case 'audio': {
          const audio = div.appendChild(document.createElement('audio'));
          audio.src = href;
          audio.controls = true;
          audio.preload = 'none';
          medias.push(audio);
          break;
        }
        case 'video': {
          const video = div.appendChild(document.createElement('video'));
          video.src = href;
          video.controls = true;
          video.preload = 'none';
          medias.push(video);
          break;
        }
        default: {
          div.classList.add('icon');
          div.dataset.type = type;
          break;
        }
      }

      const anchor = figure.appendChild(a.cloneNode(true));
    }
    this.preloadMediaMetadata(medias, options); // async

    mainElem.textContent = '';
    mainElem.appendChild(wrapper);
  },

  isHighlighted(elem) {
    return elem.classList.contains("highlight");
  },

  highlight(elem, willHighlight, {updateSelectionHint = true} = {}) {
    if (typeof willHighlight === "undefined") {
      willHighlight = !this.isHighlighted(elem);
    }

    if (willHighlight) {
      elem.classList.add("highlight");
    } else {
      elem.classList.remove("highlight");
    }

    if (updateSelectionHint) {
      const selections = document.querySelectorAll('main [data-entry].highlight').length;
      const labelElem = document.getElementById('panel-selections');
      labelElem.textContent = selections > 0 ? utils.lang('label_selected', {count: selections}) : '';
    }
  },

  getTypeFromUrl(url) {
    if (/\/$/i.test(url)) {
      return 'dir';
    }

    if (/\.(jpg|jpeg?|gif|png|bmp|ico|webp|svg)$/i.test(url)) {
      return 'image';
    }

    if (/\.(mp4|ogv|ogx|ogg|webm)$/i.test(url)) {
      return 'video';
    }

    if (/\.(wav|mp3|oga|weba)$/i.test(url)) {
      return 'audio';
    }

    return 'file';
  },

  async getRedirectedUrl(url, {catchError = true} = {}) {
    // resolve a possible redirect
    if (/\.(htm)$/i.test(url)) {
      try {
        const response = await fetch(url, {method: 'HEAD'});
        return response.url;
      } catch (ex) {
        // cross-origin, invalid, circular, or non-accessible URL
        if (catchError) {
          return url;
        }
        throw ex;
      }
    }

    return url;
  },

  syncTable() {
    const mainElem = document.querySelector('main');
    const dataTable = dataTableHandler.elem;

    // nothing to sync
    if (mainElem.contains(dataTable)) { return; }

    for (const entry of mainElem.querySelectorAll('[data-entry]')) {
      const tableEntry = dataTable.querySelector(`[data-entry][data-path="${CSS.escape(entry.dataset.path)}"]`);
      tableEntry.hidden = entry.hidden;
      this.highlight(tableEntry, this.isHighlighted(entry), {updateSelectionHint: false});
      tableEntry.parentNode.appendChild(tableEntry);
    }
  },

  async loadAnchorMetadata(anchor) {
    // skip if already loaded
    if (anchor.dataset.type) {
      return;
    }

    const href = anchor.href;
    let href2;
    try {
      href2 = await this.getRedirectedUrl(href, {catchError: false});
    } catch (ex) {
      anchor.dataset.type = 'link';
      return;
    }

    if (href !== href2) { 
      anchor.dataset.href = href2;
    }
    anchor.dataset.type = this.getTypeFromUrl(href2);
  },

  async preloadMediaMetadata(medias, {
    loadMetadata = false,
    loadTracks = true,
  } = {}) {
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');

    const loadFileListMap = new Map();
    const loadFileList = async (src) => {
      let p = loadFileListMap.get(src);
      if (p) { return p; }
      p = (async () => {
        const xhr = await utils.wsb({
          url: src + '?a=list&f=json',
          responseType: 'json',
          method: "GET",
        });
        return xhr.response.data;
      })();
      loadFileListMap.set(src, p);
      return p;
    };

    async function preloadMetadata(media) {
      // Special handling to prevent medias unplayable during native Firefox
      // preloading.
      if (utils.userAgent.is('firefox')) {
        // skip if metadata already loaded
        if (!Number.isNaN(media.duration)) {
          return;
        }

        // Media loading may halt permanently when preloading many WebM files.
        // Preload only the video poster instead.
        // https://bugzilla.mozilla.org/show_bug.cgi?id=1756988
        if (/\.webm$/i.test(media.src) && media.matches('video')) {
          return await preloadPoster(media);
        }

        return await preloadMetadataSequentially(media);
      }

      media.preload = 'metadata';
    }

    async function preloadMetadataSequentially(media) {
      let resolve, reject;
      const onloadedmetadata = (event) => {
        resolve();
      };
      const onerror = (event) => {
        reject(new Error(`Unable to load ${media.src}`));
      };
      const onabort = (event) => {
        reject(new Error(`Aborted loading ${media.src}`));
      };
      const p = new Promise((res, rej) => {
        resolve = res;
        reject = rej;
        media.addEventListener('loadedmetadata', onloadedmetadata);
        media.addEventListener('error', onerror);
        media.addEventListener('abort', onabort);
        media.preload = 'metadata';
      })
      p.catch((ex) => {}).then(() => {
        media.removeEventListener('loadedmetadata', onloadedmetadata);
        media.removeEventListener('error', onerror);
        media.removeEventListener('abort', onabort);
      });
      return await p;
    }

    async function preloadPoster(media) {
      let resolve, reject;
      const loader = document.createElement(media.tagName);
      const onloadeddata = async (event) => {
        try {
          const loader = event.target;
          const {videoWidth: w, videoHeight: h} = loader;

          // canvas is cleared when width/height is set
          canvas.width =  w;
          canvas.height = h;

          context.drawImage(loader, 0, 0, w, h);

          const dummySrc = URL.createObjectURL(new MediaSource());
          loader.src = dummySrc;
          loader.load();
          URL.revokeObjectURL(dummySrc);

          const imgBlob = await new Promise(r => canvas.toBlob(r));
          const imgSrc = URL.createObjectURL(imgBlob);
          media.poster = imgSrc;
          URL.revokeObjectURL(imgSrc);

          resolve();
        } catch (ex) {
          reject(ex);
        }
      };
      const onerror = (event) => {
        reject(new Error(`Unable to load ${media.src}`));
      };
      const onabort = (event) => {
        reject(new Error(`Aborted loading ${media.src}`));
      };
      const p = new Promise((res, rej) => {
        resolve = res;
        reject = rej;
        loader.addEventListener('loadeddata', onloadeddata);
        loader.addEventListener('error', onerror);
        loader.addEventListener('abort', onabort);
        loader.src = media.src;
      })
      p.catch((ex) => {}).then(() => {
        loader.removeEventListener('loadeddata', onloadeddata);
        loader.removeEventListener('error', onerror);
        loader.removeEventListener('abort', onabort);
      });
      return await p;
    }

    async function preloadTracks(media) {
      const u = new URL(media.src);
      /^(.*\/)([^\/]*)$/.test(u.pathname);
      u.pathname = RegExp.$1;
      u.search = u.hash = '';
      const filename = decodeURIComponent(RegExp.$2);
      const basename = filename.replace(/\.[^.]*$/, '');
      const pattern = new RegExp(utils.escapeRegExp(basename) + '\.((?:.+\.)*vtt)$', 'i');
      const dirSrc = u.href;
      let list;
      let first = true;
      try {
        list = await loadFileList(dirSrc);
      } catch (ex) {
        console.error(`Unable to fetch directory list "${dirSrc}": ${ex.message}`);
        return;
      }
      for (const {name, type} of list) {
        if (type !== 'file') { continue; }
        if (!pattern.test(name)) { continue; }
        const track = media.appendChild(document.createElement('track'));
        track.label = RegExp.$1;
        track.src = dirSrc + encodeURIComponent(name);
        track.srclang = '';
        if (first) {
          track.default = true;
          first = false;
        }
      }
    }

    // preload tracks parallelly
    if (loadTracks) {
      await Promise.all(medias.map(media => preloadTracks(media).catch ((ex) => {
        console.error(ex);
      })));
    }

    // preload metadata sequentially
    if (loadMetadata) {
      for (const media of medias) {
        await preloadMetadata(media).catch ((ex) => {
          console.error(ex);
        });
      }
    }
  },

  async expandDirs({recursively = true, includeHidden = false} = {}) {
    const mode = document.getElementById("explorer").value;
    const mainElem = document.querySelector('main');
    const dataTable = dataTableHandler.elem;

    // sync entry status if not table mode
    if (mode !== 'table') {
      this.syncTable();
    }

    for (const entry of dataTable.querySelectorAll('[data-entry]:not([data-expanded])')) {
      if (!includeHidden && entry.hidden) { continue; }
      await explorer.expandTableRow(entry, {recursively});
    }

    // reload if not table mode
    if (mode !== 'table') {
      await this.switchView(mode, {persist: false, syncTable: false});
    }
  },

  async expandTableRow(tr, {recursively = false} = {}) {
    if (tr.dataset.type !== 'dir') { return; }

    const a = tr.querySelector('a[href]');
    if (!a) { return; }

    const dirPath = tr.dataset.path + '/';

    tr.dataset.expanded = '';

    try {
      const doc = (await utils.xhr({
        url: a.href,
        responseType: 'document',
      })).response;
      const tasks = [];
      const trNext = tr.nextSibling;
      for (const trNew of doc.querySelectorAll('main [data-entry]')) {
        const anchor = trNew.querySelector('a[href]');
        if (!anchor) { continue; }

        trNew.dataset.path = dirPath + trNew.dataset.path;

        const tdDir = trNew.querySelector('td');
        tdDir.dataset.sort = dirPath + tdDir.dataset.sort;
        tdDir.querySelector('span').title = dirPath + tdDir.querySelector('span').title;

        anchor.href = anchor.href;

        tr.parentNode.insertBefore(trNew, trNext);

        if (recursively) {
          tasks.push(this.expandTableRow(trNew, {recursively}));
        }
      }
      await Promise.all(tasks);
    } catch (ex) {
      console.error(ex);
    }
  },

  get onMainClick() {
    const func = (event) => {
      const elem = event.target.closest('[data-entry]');
      if (!elem) { return; }
      this.highlight(elem);
    };
    Object.defineProperty(this, 'onMainClick', {value: func});
    return func;
  },

  get onExplorerChange() {
    const func = (event) => {
      this.switchView();
    };
    Object.defineProperty(this, 'onExplorerChange', {value: func});
    return func;
  },
};

const previewer = {
  active: false,
  mainElem: null,
  anchors: null,
  currentIndex: null,

  defaultNaturalWidth: 500,
  zoomRatio: 0.15,
  minZoomRatio: 0.01,
  movePixels: 25,

  get wrapper() {
    const wrapper = document.createElement('div');
    wrapper.classList.add('previewer');
    wrapper.dir = 'ltr';

    const figure = wrapper.appendChild(document.createElement('figure'));

    const toolbar = wrapper.appendChild(document.createElement('div'));
    toolbar.classList.add('previewer-toolbar');
    toolbar.title = utils.lang('previewer_toolbar_title');

    const toolbarPrev = toolbar.appendChild(document.createElement('button'));
    toolbarPrev.textContent = '\u23EA';
    toolbarPrev.title = utils.lang('previewer_button_previous');
    toolbarPrev.type = 'button';
    toolbarPrev.addEventListener('click', (event) => {
      this.prev();
    });

    const toolbarNext = toolbar.appendChild(document.createElement('button'));
    toolbarNext.textContent = '\u23E9';
    toolbarNext.title = utils.lang('previewer_button_next');
    toolbarNext.type = 'button';
    toolbarNext.addEventListener('click', (event) => {
      this.next();
    });

    const toolbarInfo = toolbar.appendChild(document.createElement('button'));
    toolbarInfo.textContent = '\u24D8';
    toolbarInfo.title = utils.lang('previewer_button_infobar');
    toolbarInfo.type = 'button';
    toolbarInfo.addEventListener('click', (event) => {
      this.toggleInfobar();
    });

    const toolbarClose = toolbar.appendChild(document.createElement('button'));
    toolbarClose.textContent = '\u2715';
    toolbarClose.title = utils.lang('previewer_button_close');
    toolbarClose.type = 'button';
    toolbarClose.addEventListener('click', (event) => {
      this.unpreview();
    });

    const infobar = wrapper.appendChild(document.createElement('div'));
    infobar.classList.add('previewer-infobar');

    const tooltip = wrapper.appendChild(document.createElement('div'));
    tooltip.classList.add('previewer-tooltip');
    tooltip.hidden = true;

    Object.defineProperty(this, 'wrapper', {value: wrapper});
    return wrapper;
  },

  get mutationObserver() {
    const observer = new MutationObserver((mutationList, observer) => {
      this._renewAnchors();
    });

    Object.defineProperty(this, 'mutationObserver', {value: observer});
    return observer;
  },

  toggle(willActive, {persist = true} = {}) {
    if (typeof willActive === 'undefined') {
      willActive = !this.active;
    }

    this.mainElem = document.querySelector('main');
    if (willActive) {
      this._renewAnchors();
      this.mutationObserver.observe(this.mainElem, {
        childList: true,
        attributes: true,
        subtree: true,
      });
      this.mainElem.addEventListener('click', this.onAnchorClick);
      window.addEventListener('keydown', this.onKeyDown);
      window.addEventListener('wheel', this.onWheel, {passive:false});

      document.querySelector('#tools option[value="preview-on"]').hidden = true;
      document.querySelector('#tools option[value="preview-off"]').hidden = false;

      if (persist) {
        sessionStorage.setItem('previewer', '1');
        localStorage.setItem('previewer', '1');
      }
    } else {
      this.unpreview();
      this.mutationObserver.disconnect();
      this.mainElem.removeEventListener('click', this.onAnchorClick);
      window.removeEventListener('keydown', this.onKeyDown);
      window.removeEventListener('wheel', this.onWheel);

      document.querySelector('#tools option[value="preview-on"]').hidden = false;
      document.querySelector('#tools option[value="preview-off"]').hidden = true;

      if (persist) {
        sessionStorage.removeItem('previewer');
        localStorage.removeItem('previewer');
      }
    }
  },

  async preview(index, {showTooltip = true} = {}) {
    while (index < 0 || index >= this.anchors.length) {
      return;
    }

    this.currentIndex = index;
    const anchor = this.anchors[index];
    this._clearPreviewContent();

    const wrapper = this.wrapper;
    if (!wrapper.isConnected) {
      document.body.appendChild(wrapper);
    }

    if (showTooltip) {
      this.showTooltip(`${index + 1} / ${this.anchors.length}`);
    }

    const figure = wrapper.querySelector('figure');

    await explorer.loadAnchorMetadata(anchor);
    const href = anchor.dataset.href || anchor.href;
    const type = anchor.dataset.type;

    figure.dataset.type = type;

    const infobar = wrapper.querySelector('.previewer-infobar');
    infobar.textContent = '';
    const infobarAnchor = infobar.appendChild(document.createElement('a'));
    infobarAnchor.href = href;
    infobarAnchor.textContent = infobarAnchor.title = anchor.textContent;
    infobarAnchor.target = '_blank';

    switch (type) {
      case 'image': {
        const img = figure.appendChild(document.createElement('img'));
        img.alt = anchor.textContent;
        img.dataset.ratio = 1;
        img.dataset.deltaX = 0;
        img.dataset.deltaY = 0;
        await new Promise((resolve, reject) => {
          const onload = () => {
            resolve(true);
          };
          const onerror = (ex) => {
            resolve(false);
          };
          img.addEventListener('load', onload);
          img.addEventListener('error', onerror);
          img.src = href;
        }).then(loaded => {
          if (!loaded) { return; }
          img.dataset.ratio = img.width / (img.naturalWidth || this.defaultNaturalWidth);
        });
        break;
      }
      case 'audio': {
        const audio = figure.appendChild(document.createElement('audio'));
        audio.src = href;
        audio.controls = true;
        audio.autoplay = true;
        audio.focus();
        await explorer.preloadMediaMetadata([audio]);
        break;
      }
      case 'video': {
        const video = figure.appendChild(document.createElement('video'));
        video.controls = true;
        video.autoplay = true;
        video.dataset.ratio = 1;
        video.dataset.deltaX = 0;
        video.dataset.deltaY = 0;
        video.focus();
        const p1 = new Promise((resolve, reject) => {
          const onplaying = () => {
            resolve(true);
          };
          const onerror = (ex) => {
            resolve(false);
          };
          video.addEventListener('playing', onplaying);
          video.addEventListener('error', onerror);
          video.src = href;
        }).then(loaded => {
          if (!loaded) { return; }
          video.dataset.ratio = video.offsetWidth / (video.videoWidth || this.defaultNaturalWidth);
        });
        const p2 = explorer.preloadMediaMetadata([video]);
        await Promise.all([p1, p2]);
        break;
      }
      default: {
        const div = figure.appendChild(document.createElement('div'));
        div.classList.add('icon');
        div.dataset.type = type;
        break;
      }
    }
  },

  async next() {
    return await this.preview(this.currentIndex + 1);
  },

  async prev() {
    return await this.preview(this.currentIndex - 1);
  },

  unpreview() {
    this._clearPreviewContent();
    this.currentIndex = null;
    this.wrapper.remove();
  },

  zoom(ratio, {mode = 'delta-relative-ratio', updateLastRatio = true, showTooltip = true} = {}) {
    const figure = this.wrapper.querySelector('figure');

    // determine related properties
    let media, widthProp, naturalWidthProp;
    switch (figure.dataset.type) {
      case 'image': {
        media = figure.querySelector('img');
        widthProp = 'width';
        heightProp = 'height';
        naturalWidthProp = 'naturalWidth';
        break;
      }
      case 'video': {
        media = figure.querySelector('video');
        widthProp = 'offsetWidth';
        heightProp = 'offsetHeight';
        naturalWidthProp = 'videoWidth';
        break;
      }
      default: {
        // cannot zoom this type
        return;
      }
    }

    const getCurrentRatio = (media) => {
      return media[widthProp] / (media[naturalWidthProp] || this.defaultNaturalWidth);
    };

    // apply zooming
    let newRatio;
    handleZooming: {
      // determine absolute ratio and other properties
      switch (mode) {
        case 'delta-ratio': {
          const currentRatio = getCurrentRatio(media);
          newRatio = currentRatio + ratio;
          break;
        }

        case 'delta-relative-ratio': {
          const currentRatio = getCurrentRatio(media);
          newRatio = ratio >= 0 ? currentRatio * (1 + ratio) : currentRatio / (1 - ratio);
          break;
        }

        case 'toggle-natural-last': {
          let natural;
          switch (ratio) {
            case 1: {
              natural = true;
              break;
            }
            case 0: {
              natural = false;
              break;
            }
            default: {
              const currentRatio = getCurrentRatio(media);
              natural = currentRatio !== 1;
              break;
            }
          }

          newRatio = natural ? 1 : Number(media.dataset.ratio);
          break;
        }

        case 'fit': {
          media.style.width = null;
          media.style.maxWidth = null;
          media.style.maxHeight = null;
          newRatio = getCurrentRatio(media);
          break handleZooming;
        }

        case 'absolute':
        default: {
          newRatio = ratio;
          break;
        }
      }
      newRatio = Math.max(newRatio, this.minZoomRatio);

      // apply newRatio
      media.style.width = (newRatio * (media[naturalWidthProp] || this.defaultNaturalWidth)) + 'px';
      media.style.maxWidth = 'none';
      media.style.maxHeight = 'none';
    }

    // fit new position when zoom in
    const mediaWidth = media[widthProp];
    const mediaHeight = media[heightProp];
    const totalWidth = figure.offsetWidth;
    const totalHeight = figure.offsetHeight;
    let newDeltaX = Number(media.dataset.deltaX);
    let newDeltaY = Number(media.dataset.deltaY);
    newDeltaX = Math.max(newDeltaX, -Math.abs(totalWidth - mediaWidth) / 2);
    newDeltaX = Math.min(newDeltaX, Math.abs(totalWidth - mediaWidth) / 2);
    newDeltaY = Math.max(newDeltaY, -Math.abs(totalHeight - mediaHeight) / 2);
    newDeltaY = Math.min(newDeltaY, Math.abs(totalHeight - mediaHeight) / 2);

    media.style.left = `calc(50% + ${newDeltaX}px)`;
    media.style.top = `calc(50% + ${newDeltaY}px)`;
    media.dataset.deltaX = newDeltaX;
    media.dataset.deltaY = newDeltaY;

    if (updateLastRatio) {
      media.dataset.ratio = newRatio;
    }
    if (showTooltip) {
      this.showTooltip((newRatio * 100).toFixed(0) + '%');
    }
  },

  move(deltaX, deltaY, {mode = 'delta', updateLastDelta = true, showTooltip = true} = {}) {
    const figure = this.wrapper.querySelector('figure');

    // determine related properties
    let media;
    switch (figure.dataset.type) {
      case 'image': {
        media = figure.querySelector('img');
        widthProp = 'width';
        heightProp = 'height';
        break;
      }
      case 'video': {
        media = figure.querySelector('video');
        widthProp = 'offsetWidth';
        heightProp = 'offsetHeight';
        break;
      }
      default: {
        // cannot move this type
        return;
      }
    }

    // apply moving
    let newDeltaX, newDeltaY;
    handleZooming: {
      switch (mode) {
        case 'delta': {
          newDeltaX = Number(media.dataset.deltaX) + deltaX;
          newDeltaY = Number(media.dataset.deltaY) + deltaY;
          break;
        }
        case 'absolute':
        default: {
          newDeltaX = deltaX;
          newDeltaY = deltaY;
          break;
        }
      }

      // fit new position
      const mediaWidth = media[widthProp];
      const mediaHeight = media[heightProp];
      const totalWidth = figure.offsetWidth;
      const totalHeight = figure.offsetHeight;
      newDeltaX = Math.max(newDeltaX, -Math.abs(totalWidth - mediaWidth) / 2);
      newDeltaX = Math.min(newDeltaX, Math.abs(totalWidth - mediaWidth) / 2);
      newDeltaY = Math.max(newDeltaY, -Math.abs(totalHeight - mediaHeight) / 2);
      newDeltaY = Math.min(newDeltaY, Math.abs(totalHeight - mediaHeight) / 2);

      // apply new position
      media.style.left = `calc(50% + ${newDeltaX}px)`;
      media.style.top = `calc(50% + ${newDeltaY}px)`;
    }

    if (updateLastDelta) {
      media.dataset.deltaX = newDeltaX;
      media.dataset.deltaY = newDeltaY;
    }
    if (showTooltip) {
      this.showTooltip(`(${newDeltaX}, ${newDeltaY})`);
    }
  },

  toggleInfobar(willShow) {
    if (typeof willShow === 'undefined') {
      willShow = !this.wrapper.classList.contains('show-infobar');
    }

    if (willShow) {
      this.wrapper.classList.add('show-infobar');
    } else {
      this.wrapper.classList.remove('show-infobar');
    }
  },

  showTooltip(msg) {
    if (this.showTooltip.timer) {
      clearTimeout(this.showTooltip.timer);
    }
    const tooltip = this.wrapper.querySelector('.previewer-tooltip');
    tooltip.textContent = msg;
    tooltip.hidden = false;
    this.showTooltip.timer = setTimeout(() => {
      tooltip.hidden = true;
    }, 1000);
  },

  get onAnchorClick() {
    const func = (event) => {
      const anchor = event.target.closest('a[href]');
      if (!anchor) { return; }

      const entry = anchor.closest('[data-entry]');

      // enter directly for directory
      if (entry.dataset.type === 'dir') {
        return;
      }

      const index = this.anchors.indexOf(anchor);

      // not registered item
      if (index === -1) {
        return;
      }

      event.preventDefault();
      this.preview(index);
    };
    Object.defineProperty(this, 'onAnchorClick', {value: func});
    return func;
  },

  get onKeyDown() {
    const func = (event) => {
      // skip if not previewing
      if (this.currentIndex === null) { 
        return;
      }

      switch (event.key) {
        case 'Escape': {
          event.preventDefault();
          this.unpreview();
          break;
        }

        case 'Home': {
          event.preventDefault();
          this.preview(0);
          break;
        }

        case 'End': {
          event.preventDefault();
          this.preview(this.anchors.length - 1);
          break;
        }

        case 'PageUp': {
          event.preventDefault();
          this.prev();
          break;
        }

        case 'PageDown': {
          event.preventDefault();
          this.next();
          break;
        }

        case 'i': {
          event.preventDefault();
          this.toggleInfobar();
          break;
        }

        case ' ': {
          // skip if focusing a media to prevent interruption of control
          if (document.activeElement.closest('audio, video')) {
            break;
          }

          event.preventDefault();
          this.toggleInfobar();
          break;
        }

        case 'Enter': {
          const anchor = this.wrapper.querySelector('.previewer-infobar a[href]');
          if (!anchor) { break; }

          event.preventDefault();
          anchor.click();
          break;
        }

        case '+': {
          event.preventDefault();
          this.zoom(this.zoomRatio);
          break;
        }

        case '-': {
          event.preventDefault();
          this.zoom(-this.zoomRatio);
          break;
        }

        case '0': {
          if (!(event.ctrlKey || event.metaKey)) {
            break;
          }
          event.preventDefault();
          this.zoom(null, {mode: 'fit', updateLastRatio: false});
          break;
        }

        case '1': {
          if (!(event.ctrlKey || event.metaKey)) {
            break;
          }
          event.preventDefault();
          this.zoom(null, {mode: 'toggle-natural-last', updateLastRatio: false});
          break;
        }

        case 'ArrowLeft': {
          // move if Ctrl/Command/Shift is hold
          if (event.ctrlKey || event.metaKey || event.shiftKey) {
            event.preventDefault();
            this.move(-this.movePixels, 0);
            break;
          }

          // skip if focusing a media to prevent interruption of control
          if (document.activeElement.closest('audio, video') && !event.altKey) {
            break;
          }

          event.preventDefault();
          this.prev();
          break;
        }

        case 'ArrowRight': {
          // move if Ctrl/Command/Shift is hold
          if (event.ctrlKey || event.metaKey || event.shiftKey) {
            event.preventDefault();
            this.move(+this.movePixels, 0);
            break;
          }

          // skip if focusing a media to prevent interruption of control
          if (document.activeElement.closest('audio, video') && !event.altKey) {
            break;
          }

          event.preventDefault();
          this.next();
          break;
        }

        case 'ArrowUp': {
          // move if Ctrl/Command/Shift is hold
          if (event.ctrlKey || event.metaKey || event.shiftKey) {
            event.preventDefault();
            this.move(0, -this.movePixels);
            break;
          }

          // skip if focusing a media to prevent interruption of control
          if (document.activeElement.closest('audio, video') && !event.altKey) {
            break;
          }

          event.preventDefault();
          this.zoom(this.zoomRatio);
          break;
        }

        case 'ArrowDown': {
          // move if Ctrl/Command/Shift is hold
          if (event.ctrlKey || event.metaKey || event.shiftKey) {
            event.preventDefault();
            this.move(0, +this.movePixels);
            break;
          }

          // skip if focusing a media to prevent interruption of control
          if (document.activeElement.closest('audio, video') && !event.altKey) {
            break;
          }

          event.preventDefault();
          this.zoom(-this.zoomRatio);
          break;
        }
      }
    };
    Object.defineProperty(this, 'onKeyDown', {value: func});
    return func;
  },

  get onWheel() {
    const func = (event) => {
      // skip if not previewing
      if (this.currentIndex === null) {
        return;
      }

      // wheel down
      if (event.deltaY > 0) {
        event.preventDefault();
        this.zoom(-this.zoomRatio);
        return;
      }

      // wheel up
      if (event.deltaY < 0) {
        event.preventDefault();
        this.zoom(this.zoomRatio);
        return;
      }
    };
    Object.defineProperty(this, 'onWheel', {value: func});
    return func;
  },

  _renewAnchors() {
    this.anchors = Array.from(this.mainElem.querySelectorAll('[data-entry]:not([hidden]) a[href]'));
  },

  _clearPreviewContent() {
    const wrapper = this.wrapper;

    const figure = wrapper.querySelector('figure');

    // in case media still playing after removed
    for (const media of figure.querySelectorAll('audio, video')) {
      media.pause();
    }

    figure.textContent = '';
  },
};

function onToolsChange(event) {
  event.preventDefault();
  const command = event.target.value;
  event.target.value = '';

  const func = onToolsChange.commands[command];
  func();
}

onToolsChange.commands = {
  'preview-on': function previewOn() {
    previewer.toggle(true);
  },

  'preview-off': function previewOff() {
    previewer.toggle(false);
  },

  'select-all': function selectAll() {
    for (const entry of document.querySelectorAll('main [data-entry]:not([hidden])')) {
      explorer.highlight(entry, true);
    }
  },

  'deselect-all': function deselectAll() {
    for (const entry of document.querySelectorAll('main [data-entry]')) {
      explorer.highlight(entry, false);
    }
  },

  'expand-all': async function expandAll() {
    await explorer.expandDirs();
  },

  'filter': function filter() {
    const kw = prompt(utils.lang('tools_filter_prompt'));
    if (kw === null) { return; }
    let regex;
    if (/^\/(.*)\/([a-z]*)$/i.test(kw)) {
      try {
        regex = new RegExp(RegExp.$1, RegExp.$2);
      } catch (ex) {
        alert(`Invalid regex "${kw}": ${ex.message}`);
        return;
      }
    } else {
      regex = new RegExp(utils.escapeRegExp(kw), 'i');
    }
    for (const entry of document.querySelectorAll('main [data-entry]:not([hidden])')) {
      const filename = entry.dataset.path.replace(/^.*\//, '');
      regex.lastIndex = 0;
      if (!regex.test(filename)) {
        entry.hidden = true;
        explorer.highlight(entry, false);
      }
    }
  },

  'filter-clear': function filterClear() {
    for (const entry of document.querySelectorAll('main [data-entry][hidden]')) {
      entry.hidden = false;
    }
  },
};

function onCommandFocus(event) {
  const cmdElem = document.getElementById('command');
  const selectedEntries = document.querySelectorAll('main .highlight');

  switch (selectedEntries.length) {
    case 0: {
      cmdElem.querySelector('[value="mkdir"]').hidden = false;
      cmdElem.querySelector('[value="mkzip"]').hidden = false;
      cmdElem.querySelector('[value="mkfile"]').hidden = false;
      cmdElem.querySelector('[value="upload"]').hidden = false;
      cmdElem.querySelector('[value="uploaddir"]').hidden = false;
      cmdElem.querySelector('[value="source"]').hidden = true;
      cmdElem.querySelector('[value="download"]').hidden = true;
      cmdElem.querySelector('[value="exec"]').hidden = true;
      cmdElem.querySelector('[value="browse"]').hidden = true;
      cmdElem.querySelector('[value="edit"]').hidden = true;
      cmdElem.querySelector('[value="editx"]').hidden = true;
      cmdElem.querySelector('[value="move"]').hidden = true;
      cmdElem.querySelector('[value="copy"]').hidden = true;
      cmdElem.querySelector('[value="link"]').hidden = true;
      cmdElem.querySelector('[value="delete"]').hidden = true;
      break;
    }

    case 1: {
      const elem = selectedEntries[0];
      const isHtml = /\.(?:x?html?|xht)$/i.test(elem.dataset.path);
      cmdElem.querySelector('[value="mkdir"]').hidden = true;
      cmdElem.querySelector('[value="mkzip"]').hidden = true;
      cmdElem.querySelector('[value="mkfile"]').hidden = true;
      cmdElem.querySelector('[value="upload"]').hidden = true;
      cmdElem.querySelector('[value="uploaddir"]').hidden = true;
      cmdElem.querySelector('[value="exec"]').hidden = false;
      cmdElem.querySelector('[value="browse"]').hidden = false;
      cmdElem.querySelector('[value="download"]').hidden = false;
      cmdElem.querySelector('[value="move"]').hidden = false;
      cmdElem.querySelector('[value="copy"]').hidden = false;
      cmdElem.querySelector('[value="link"]').hidden = false;
      cmdElem.querySelector('[value="delete"]').hidden = false;
      if (elem.dataset.type === 'link') {
        cmdElem.querySelector('[value="source"]').hidden = false;
        cmdElem.querySelector('[value="edit"]').hidden = true;
        cmdElem.querySelector('[value="editx"]').hidden = true;
      } else if (elem.dataset.type === 'file') {
        cmdElem.querySelector('[value="source"]').hidden = false;
        cmdElem.querySelector('[value="edit"]').hidden = false;
        cmdElem.querySelector('[value="editx"]').hidden = !isHtml;
      } else if (elem.dataset.type === 'dir') {
        cmdElem.querySelector('[value="source"]').hidden = true;
        cmdElem.querySelector('[value="edit"]').hidden = true;
        cmdElem.querySelector('[value="editx"]').hidden = true;
      }
      break;
    }

    default: { // multiple
      cmdElem.querySelector('[value="mkdir"]').hidden = true;
      cmdElem.querySelector('[value="mkzip"]').hidden = true;
      cmdElem.querySelector('[value="mkfile"]').hidden = true;
      cmdElem.querySelector('[value="upload"]').hidden = true;
      cmdElem.querySelector('[value="uploaddir"]').hidden = true;
      cmdElem.querySelector('[value="source"]').hidden = true;
      cmdElem.querySelector('[value="download"]').hidden = false;
      cmdElem.querySelector('[value="exec"]').hidden = true;
      cmdElem.querySelector('[value="browse"]').hidden = true;
      cmdElem.querySelector('[value="edit"]').hidden = true;
      cmdElem.querySelector('[value="editx"]').hidden = true;
      cmdElem.querySelector('[value="move"]').hidden = false;
      cmdElem.querySelector('[value="copy"]').hidden = false;
      cmdElem.querySelector('[value="link"]').hidden = false;
      cmdElem.querySelector('[value="delete"]').hidden = false;
      break;
    }
  }
}

function onCommandChange(event) {
  event.preventDefault();
  const command = event.target.value;
  event.target.value = '';

  switch (command) {
    case 'upload': {
      const elem = document.getElementById('upload-file-selector');
      elem.value = '';
      elem.click();
      break;
    }

    case 'uploaddir': {
      const elem = document.getElementById('upload-dir-selector');
      elem.value = '';
      elem.click();
      break;
    }

    default: {
      return onCommandRun({cmd: command});
      break;
    }
  }
}

async function onCommandRun(detail) {
  const command = detail.cmd;
  const func = onCommandRun.commands[command];
  const selectedEntries = document.querySelectorAll('main .highlight');
  const commandElem = document.getElementById("command");
  commandElem.disabled = true;
  try {
    await func(selectedEntries, detail);
  } catch (ex) {
    console.error(ex);
  }
  commandElem.disabled = false;
}

onCommandRun.upload = async function upload(entries) {
  const base = document.querySelector('main').dataset.base;
  const dir = document.querySelector('main').dataset.path;
  const errors = [];
  for (const {path, file} of entries) {
    const newPath = dir + path;
    const target = location.origin + (base + newPath).split('/').map(x => encodeURIComponent(x)).join('/');
    try {
      // directory
      if (!file) {
        const formData = new FormData();
        formData.append('token', await utils.acquireToken(target));

        await utils.wsb({
          url: target + '?a=mkdir&f=json',
          responseType: 'json',
          method: "POST",
          formData: formData,
        });

        continue;
      }

      const formData = new FormData();
      formData.append('token', await utils.acquireToken(target));
      formData.append('upload', file);

      await utils.wsb({
        url: target + '?a=save&f=json',
        responseType: 'json',
        method: "POST",
        formData: formData,
      });
    } catch (ex) {
      errors.push(`"${newPath}": ${ex.message}`);
    }
  }
  if (errors.length) {
    const msg = entries.length === 1 ?
      'Unable to upload file ' + errors.join('\n'):
      'Unable to upload files:\n' + errors.join('\n');
    alert(msg);
    if (errors.length === entries.length) {
      return;
    }
  }
  location.reload();
};

onCommandRun.sortEntries = function sortEntries(a, b) {
  const ka = a.oldPath;
  const kb = b.oldPath;
  if (ka < kb) { return -1; }
  if (ka > kb) { return 1; }
  return 0;
};

onCommandRun.commands = {
  async source(selectedEntries) {
    const target = selectedEntries[0].querySelector('a[href]').href;
    location.href = target + '?a=source';
  },

  async download(selectedEntries) {
    if (selectedEntries.length === 1) {
      const target = selectedEntries[0].querySelector('a[href]').href;
      location.href = target + '?a=download';
    } else {
      const u = new URL(utils.getTargetUrl(location.href));
      u.searchParams.append('a', 'download');
      for (const entry of selectedEntries) {
        u.searchParams.append('i', entry.dataset.path);
      }
      location.href = u.href;
    }
  },

  async exec(selectedEntries) {
    const base = document.querySelector('main').dataset.base;
    const dir = document.querySelector('main').dataset.path;
    const oldPath = dir + selectedEntries[0].dataset.path;
    const target = selectedEntries[0].querySelector('a[href]').href;
    try {
      await utils.wsb({
        url: target + '?a=exec&f=json',
        responseType: 'json',
        method: "GET",
      });
    } catch (ex) {
      alert(`Unable to run "${oldPath}": ${ex.message}`);
    }
  },

  async browse(selectedEntries) {
    const base = document.querySelector('main').dataset.base;
    const dir = document.querySelector('main').dataset.path;
    const oldPath = dir + selectedEntries[0].dataset.path;
    const target = location.origin + (base + oldPath).split('/').map(x => encodeURIComponent(x)).join('/');
    try {
      await utils.wsb({
        url: target + '?a=browse&f=json',
        responseType: 'json',
        method: "GET",
      });
    } catch (ex) {
      alert(`Unable to browse "${oldPath}": ${ex.message}`);
    }
  },

  async mkdir(selectedEntries) {
    let newPath = prompt(utils.lang('command_mkdir_prompt'), utils.lang('command_mkdir_default'));
    if (!newPath) {
      return;
    }

    const base = document.querySelector('main').dataset.base;
    const dir = document.querySelector('main').dataset.path;
    newPath = dir + newPath;
    const target = location.origin + (base + newPath).split('/').map(x => encodeURIComponent(x)).join('/');

    try {
      const formData = new FormData();
      formData.append('token', await utils.acquireToken(target));

      await utils.wsb({
        url: target + '?a=mkdir&f=json',
        responseType: 'json',
        method: "POST",
        formData: formData,
      });
    } catch (ex) {
      alert(`Unable to create directory "${newPath}": ${ex.message}`);
      return;
    }
    location.reload();
  },

  async mkzip(selectedEntries) {
    let newPath = prompt(utils.lang('command_mkzip_prompt'), utils.lang('command_mkzip_default'));
    if (!newPath) {
      return;
    }

    const base = document.querySelector('main').dataset.base;
    const dir = document.querySelector('main').dataset.path;
    newPath = dir + newPath;
    const target = location.origin + (base + newPath).split('/').map(x => encodeURIComponent(x)).join('/');

    try {
      // throw if target exists
      const info = (await utils.wsb({
        url: target + '?a=info&f=json',
        responseType: 'json',
        method: "GET",
      })).response.data;
      if (info.type !== null) {
        throw new Error('Found something at target.');
      }

      const formData = new FormData();
      formData.append('token', await utils.acquireToken(target));

      await utils.wsb({
        url: target + '?a=mkzip&f=json',
        responseType: 'json',
        method: "POST",
        formData: formData,
      });
    } catch (ex) {
      alert(`Unable to create ZIP "${newPath}": ${ex.message}`);
      return;
    }
    location.reload();
  },

  async mkfile(selectedEntries) {
    let newPath = prompt(utils.lang('command_mkfile_prompt'), utils.lang('command_mkfile_default'));
    if (!newPath) {
      return;
    }

    const base = document.querySelector('main').dataset.base;
    const dir = document.querySelector('main').dataset.path;
    newPath = dir + newPath;
    const target = location.origin + (base + newPath).split('/').map(x => encodeURIComponent(x)).join('/');

    try {
      // throw if target exists
      const info = (await utils.wsb({
        url: target + '?a=info&f=json',
        responseType: 'json',
        method: "GET",
      })).response.data;
      if (info.type !== null) {
        throw new Error('Found something at target.');
      }

      location.href = target + '?a=edit&back=' + encodeURIComponent(location.href);
    } catch (ex) {
      alert(`Unable to create file "${newPath}": ${ex.message}`);
      return;
    }
  },

  async edit(selectedEntries) {
    const base = document.querySelector('main').dataset.base;
    const dir = document.querySelector('main').dataset.path;
    const oldPath = dir + selectedEntries[0].dataset.path;
    const target = location.origin + (base + oldPath).split('/').map(x => encodeURIComponent(x)).join('/');
    location.href = target + '?a=edit&back=' + encodeURIComponent(location.href);
  },

  async editx(selectedEntries) {
    const base = document.querySelector('main').dataset.base;
    const dir = document.querySelector('main').dataset.path;
    const oldPath = dir + selectedEntries[0].dataset.path;
    const target = location.origin + (base + oldPath).split('/').map(x => encodeURIComponent(x)).join('/');
    location.href = target + '?a=editx&back=' + encodeURIComponent(location.href);
  },

  async upload(selectedEntries, {files}) {
    const entries = Array.prototype.map.call(files, (file) => {
      const path = file.name;
      return {path, file};
    });
    return await onCommandRun.upload(entries);
  },

  async uploaddir(selectedEntries, {files}) {
    const entries = Array.prototype.map.call(files, (file) => {
      const path = file.webkitRelativePath;
      return {path, file};
    });
    return await onCommandRun.upload(entries);
  },

  async uploadx(selectedEntries, {files}) {
    const entries = [];
    const addEntry = async (entry) => {
      const path = entry.fullPath.slice(1); // remove starting '/'
      if (entry.isDirectory) {
        const reader = entry.createReader();
        let hasSubEntry = false;
        while (true) {
          const subEntries = await new Promise((resolve, reject) => {
            reader.readEntries(resolve, reject);
          });
          if (!subEntries.length) { break; }
          hasSubEntry = true;
          for (const subEntry of subEntries) {
            await addEntry(subEntry);
          }
        }
        // add an entry for empty directory
        if (!hasSubEntry) {
          entries.push({path, file: null});
        }
      } else {
        const file = await new Promise((resolve, reject) => {
          entry.file(resolve, reject);
        });
        entries.push({path, file});
      }
    };
    for (const entry of files) {
      await addEntry(entry);
    }
    return await onCommandRun.upload(entries);
  },

  async move(selectedEntries) {
    const moveEntry = async (oldPath, newPath) => {
      const target = location.origin + (base + oldPath).split('/').map(x => encodeURIComponent(x)).join('/');
      const formData = new FormData();
      formData.append('token', await utils.acquireToken(target));
      formData.append('target', newPath);

      await utils.wsb({
        url: target + '?a=move&f=json',
        responseType: 'json',
        method: "POST",
        formData,
      });
    };

    const base = document.querySelector('main').dataset.base;
    const dir = document.querySelector('main').dataset.path;
    if (selectedEntries.length === 1) {
      const oldPath = dir + selectedEntries[0].dataset.path;
      const newPath = prompt(utils.lang('command_move_prompt'), oldPath);
      if (!newPath) {
        return;
      }

      try {
        await moveEntry(oldPath, newPath);
      } catch (ex) {
        alert(`Unable to move "${oldPath}" => "${newPath}": ${ex.message}`);
        return;
      }
    } else {
      let newDir = prompt(utils.lang('command_move_prompt_multi'), dir);
      if (!newDir) {
        return;
      }

      newDir = newDir.replace(/\/+$/, '') + '/';

      // create the target directory
      try {
        const target = location.origin + (base + newDir).split('/').map(x => encodeURIComponent(x)).join('/');
        const formData = new FormData();
        formData.append('token', await utils.acquireToken(target));

        await utils.wsb({
          url: target + '?a=mkdir&f=json',
          responseType: 'json',
          method: "POST",
          formData: formData,
        });
      } catch (ex) {
        alert(`Unable to move to "${newDir}": ${ex.message}`);
        return;
      }

      const entries = Array.prototype.map.call(selectedEntries, entry => {
        const oldPath = dir + entry.dataset.path;
        const newPath = newDir + oldPath.replace(/^.*\//, '');
        return {oldPath, newPath};
      });
      const errors = [];
      for (const {oldPath, newPath} of entries.sort(onCommandRun.sortEntries).reverse()) {
        try {
          await moveEntry(oldPath, newDir);
        } catch (ex) {
          errors.push(`"${oldPath}" => "${newPath}": ${ex.message}`);
        }
      }
      if (errors.length) {
        const msg = 'Unable to move entries:\n' + errors.reverse().join('\n');
        alert(msg);
        if (errors.length === entries.length) {
          return;
        }
      }
    }
    location.reload();
  },

  async copy(selectedEntries) {
    const copyEntry = async (oldPath, newPath) => {
      const target = location.origin + (base + oldPath).split('/').map(x => encodeURIComponent(x)).join('/');
      const formData = new FormData();
      formData.append('token', await utils.acquireToken(target));
      formData.append('target', newPath);

      await utils.wsb({
        url: target + '?a=copy&f=json',
        responseType: 'json',
        method: "POST",
        formData,
      });
    };

    const base = document.querySelector('main').dataset.base;
    const dir = document.querySelector('main').dataset.path;
    if (selectedEntries.length === 1) {
      const oldPath = dir + selectedEntries[0].dataset.path;
      const newPath = prompt(utils.lang('command_copy_prompt'), oldPath);
      if (!newPath) {
        return;
      }

      try {
        await copyEntry(oldPath, newPath);
      } catch (ex) {
        alert(`Unable to copy "${oldPath}" => "${newPath}": ${ex.message}`);
        return;
      }
    } else {
      let newDir = prompt(utils.lang('command_copy_prompt_multi'), dir);
      if (!newDir) {
        return;
      }

      newDir = newDir.replace(/\/+$/, '') + '/';

      // create the target directory
      try {
        const target = location.origin + (base + newDir).split('/').map(x => encodeURIComponent(x)).join('/');
        const formData = new FormData();
        formData.append('token', await utils.acquireToken(target));

        await utils.wsb({
          url: target + '?a=mkdir&f=json',
          responseType: 'json',
          method: "POST",
          formData: formData,
        });
      } catch (ex) {
        alert(`Unable to move to "${newDir}": ${ex.message}`);
        return;
      }

      const entries = Array.prototype.map.call(selectedEntries, entry => {
        const oldPath = dir + entry.dataset.path;
        const newPath = newDir + oldPath.replace(/^.*\//, '');
        return {oldPath, newPath};
      });
      const errors = [];
      for (const {oldPath, newPath} of entries.sort(onCommandRun.sortEntries).reverse()) {
        try {
          await copyEntry(oldPath, newDir);
        } catch (ex) {
          errors.push(`"${oldPath}" => "${newPath}": ${ex.message}`);
        }
      }
      if (errors.length) {
        const msg = 'Unable to copy entries:\n' + errors.reverse().join('\n');
        alert(msg);
        if (errors.length === entries.length) {
          return;
        }
      }
    }
    location.reload();
  },

  async link(selectedEntries) {
    const getRelativePath = (target, base) => {
      const targetPathParts = target.split('/');
      const basePathParts = base.split('/');

      let commonIndex;
      basePathParts.every((v, i) => {
        if (v === targetPathParts[i]) {
          commonIndex = i;
          return true;
        }
        return false;
      });

      let pathname = '../'.repeat(basePathParts.length - commonIndex - 2);
      pathname += targetPathParts.slice(commonIndex + 1).join('/');
      return pathname;
    };

    const linkEntry = async (oldPath, newPath) => {
      const target = location.origin + (base + newPath).split('/').map(x => encodeURIComponent(x)).join('/');

      // throw if target exists
      const info = (await utils.wsb({
        url: target + '?a=info&f=json',
        responseType: 'json',
        method: "GET",
      })).response.data;
      if (info.type !== null) {
        throw new Error('Found something at target.');
      }

      const url = getRelativePath(oldPath, newPath).replace(/[%#?]+/g, x => encodeURIComponent(x));
      const content = '<meta charset="UTF-8"><meta http-equiv="refresh" content="0; url=' + url + '">';

      const formData = new FormData();
      formData.append('token', await utils.acquireToken(target));
      // encode the text as ISO-8859-1 (byte string) so that it's 100% recovered
      formData.append('text', unescape(encodeURIComponent(content)));

      await utils.wsb({
        url: target + '?a=save&f=json',
        responseType: 'json',
        method: "POST",
        formData: formData,
      });
    };

    const base = document.querySelector('main').dataset.base;
    const dir = document.querySelector('main').dataset.path;
    if (selectedEntries.length === 1) {
      const oldPath = dir + selectedEntries[0].dataset.path;
      let newPath = oldPath + '.lnk.htm';
      newPath = prompt(utils.lang('command_link_prompt'), newPath);
      if (!newPath) {
        return;
      }

      try {
        // adjust newPath if it's a directory
        const target = location.origin + (base + newPath).split('/').map(x => encodeURIComponent(x)).join('/');
        const info = (await utils.wsb({
          url: target + '?a=info&f=json',
          responseType: 'json',
          method: "GET",
        })).response.data;
        if (info.type === 'dir') {
          newPath = newPath.replace(/\/+$/, '') + '/' + oldPath.replace(/^.*\//, '') + '.lnk.htm';
        }

        await linkEntry(oldPath, newPath);
      } catch (ex) {
        alert(`Unable to create link "${oldPath}" => "${newPath}": ${ex.message}`);
        return;
      }
    } else {
      let newDir = prompt(utils.lang('command_link_prompt_multi'), dir);
      if (!newDir) {
        return;
      }

      newDir = newDir.replace(/\/+$/, '') + '/';
      const entries = Array.prototype.map.call(selectedEntries, entry => {
        const oldPath = dir + entry.dataset.path;
        const newPath = newDir + oldPath.replace(/^.*\//, '') + '.lnk.htm';
        return {oldPath, newPath};
      });
      const errors = [];
      for (const {oldPath, newPath} of entries.sort(onCommandRun.sortEntries).reverse()) {
        try {
          await linkEntry(oldPath, newPath);
        } catch (ex) {
          errors.push(`"${oldPath}" => "${newPath}": ${ex.message}`);
        }
      }
      if (errors.length) {
        const msg = 'Unable to create links:\n' + errors.reverse().join('\n');
        alert(msg);
        if (errors.length === entries.length) {
          return;
        }
      }
    }
    location.reload();
  },

  async delete(selectedEntries) {
    const base = document.querySelector('main').dataset.base;
    const dir = document.querySelector('main').dataset.path;
    const entries = Array.prototype.map.call(selectedEntries, entry => {
      const oldPath = dir + entry.dataset.path;
      return {oldPath};
    });
    const errors = [];
    for (const {oldPath} of entries.sort(onCommandRun.sortEntries).reverse()) {
      try {
        const target = location.origin + (base + oldPath).split('/').map(x => encodeURIComponent(x)).join('/');
        const formData = new FormData();
        formData.append('token', await utils.acquireToken(target));

        await utils.wsb({
          url: target + '?a=delete&f=json',
          responseType: 'json',
          method: "POST",
          formData: formData,
        });
      } catch (ex) {
        errors.push(`"${oldPath}": ${ex.message}`);
      }
    }
    if (errors.length) {
      const msg = entries.length === 1 ?
        'Unable to delete ' + errors.join('\n'):
        'Unable to delete entries:\n' + errors.reverse().join('\n');
      alert(msg);
      if (errors.length === entries.length) {
        return;
      }
    }
    location.reload();
  },
};

function onUploadFileChange(event) {
  event.preventDefault();
  return onCommandRun({cmd: 'upload', files: event.target.files});
}

function onUploadDirChange(event) {
  event.preventDefault();
  return onCommandRun({cmd: 'uploaddir', files: event.target.files});
}

function onDragOver(event) {
  if (event.dataTransfer.types.includes('Files')) {
    event.preventDefault(); // required to allow drop
    event.dataTransfer.dropEffect = 'copy';
    return;
  }

  event.dataTransfer.dropEffect = 'none';
}

function onDrop(event) {
  event.preventDefault();

  // skip if command disabled
  if (document.getElementById("command").disabled) {
    return;
  }

  return onCommandRun({
    cmd: 'uploadx',
    files: Array.prototype.map.call(event.dataTransfer.items, x => x.webkitGetAsEntry()),
  });
}
