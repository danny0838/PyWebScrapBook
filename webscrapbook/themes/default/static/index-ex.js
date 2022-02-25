/**
 * Support viewer and command. Require ES8.
 */
let dataViewer;

document.addEventListener("DOMContentLoaded", function () {
  /* Extend data table to support selection */
  dataTable.tBodies[0].addEventListener("click", onDataTableBodyClick, false);

  /* Media viewers */
  dataViewer = dataTable;
  viewerInit();
  document.getElementById("viewer").addEventListener("change", onViewerChange, false);

  /* Tools */
  document.getElementById("tools").addEventListener("change", onToolsChange, false);

  /* Command handler */
  document.getElementById("command").addEventListener("focus", onCommandFocus, false);
  document.getElementById("command").addEventListener("change", onCommandChange, false);
  document.getElementById('upload-file-selector').addEventListener('change', onUploadFileChange, false);

  /* Show panel if init ok */
  document.getElementById("panel").hidden = false;
}, false);

function onDataTableBodyClick(event) {
  let elem = event.target;
  if (elem.tagName.toLowerCase() !== 'tr') {
    elem = elem.closest('tr');
  }
  highlightElem(elem);
}

function highlightElem(elem, willHighlight) {
  if (typeof willHighlight === "undefined") {
    willHighlight = !elem.classList.contains("highlight");
  }

  if (willHighlight) {
    elem.classList.add("highlight");
  } else {
    elem.classList.remove("highlight");
  }
}

function getTypeFromUrl(url) {
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
}

async function getRedirectedUrl(url, {catchError = true} = {}) {
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
}

async function loadAnchorMetadata(anchor) {
  // skip if already loaded
  if (anchor.dataset.type) {
    return;
  }

  const href = anchor.href;
  let href2;
  try {
    href2 = await getRedirectedUrl(href, {catchError: false});
  } catch (ex) {
    anchor.dataset.type = 'link';
    return;
  }

  if (href !== href2) { 
    anchor.dataset.href = href2;
  }
  anchor.dataset.type = getTypeFromUrl(href2);
}

function viewerInit() {
  const dir = document.getElementById('data-table').getAttribute('data-path');

  /* handle .htd */
  if (/\.(htd)\/?$/i.test(dir)) {
    // if there's index.html, redirect to view it
    const indexAnchor = dataTable.querySelector('tbody tr a[href="index.html"]');
    if (indexAnchor) {
      location.replace(indexAnchor.href);
      return;
    }

    // otherwise, use gallery view
    viewerApply('gallery');
  }
}

function viewerApply(mode) {
  if (!mode) {
    mode = document.getElementById("viewer").value;
  } else {
    document.getElementById("viewer").value = mode;
  }

  switch (mode) {
    case "gallery":
      viewerGallery();
      break;
    case "gallery2":
      viewerGallery({loadMetadata: true});
      break;
    case "list":
      viewerList();
      break;
    case "list2":
      viewerList({loadMetadata: true});
      break;
    default:
      viewerDefault();
      break;
  }
}

function viewerDefault() {
  if (dataViewer === dataTable) { return; }

  document.getElementById('tools').disabled = false;
  document.getElementById('command').disabled = false;

  dataViewer.parentNode.replaceChild(dataTable, dataViewer);
  dataViewer = dataTable;
}

async function viewerGallery(options = {}) {
  document.getElementById('tools').disabled = true;
  document.getElementById('command').disabled = true;

  const wrapper = document.createElement('div');
  wrapper.id = "img-gallery-view";

  const addFigure = (type) => {
    const figure = wrapper.appendChild(document.createElement('figure'));
    figure.classList.add(type);
    return figure;
  };

  const addAnchor = (a, type) => {
    const href = a.dataset.href || a.href;

    const figure = addFigure(type);

    const anchor = figure.appendChild(document.createElement('a'));
    anchor.href = href;
    anchor.target = "_blank";
    anchor.title = a.textContent;

    const div = anchor.appendChild(document.createElement('div'));
    div.classList.add('icon');
    div.classList.add(type);

    const span = anchor.appendChild(document.createElement('span'));
    span.textContent = a.textContent;

    return figure;
  };

  const addImage = (a, type) => {
    const href = a.dataset.href || a.href;

    const figure = addFigure(type);

    const anchor = figure.appendChild(document.createElement('a'));
    anchor.href = href;
    anchor.target = "_blank";
    anchor.title = a.textContent;

    const div = anchor.appendChild(document.createElement('div'));

    const img = div.appendChild(document.createElement('img'));
    img.src = href;
    img.alt = a.textContent;

    const span = anchor.appendChild(document.createElement('span'));
    span.textContent = a.textContent;

    return figure;
  };

  const addAudio = (a, type) => {
    const href = a.dataset.href || a.href;

    const figure = addFigure(type);

    const div = figure.appendChild(document.createElement('div'));

    const audio = div.appendChild(document.createElement('audio'));
    audio.src = href;
    audio.controls = true;
    audio.preload = 'none';

    const anchor = figure.appendChild(document.createElement('a'));
    anchor.href = href;
    anchor.target = "_blank";
    anchor.title = a.textContent;

    const span = anchor.appendChild(document.createElement('span'));
    span.textContent = a.textContent;

    return figure;
  };

  const addVideo = (a, type) => {
    const href = a.dataset.href || a.href;

    const figure = addFigure(type);

    const div = figure.appendChild(document.createElement('div'));

    const video = div.appendChild(document.createElement('video'));
    video.src = href;
    video.controls = true;
    video.preload = 'none';

    const anchor = figure.appendChild(document.createElement('a'));
    anchor.href = href;
    anchor.target = "_blank";
    anchor.title = a.textContent;

    const span = anchor.appendChild(document.createElement('span'));
    span.textContent = a.textContent;

    return figure;
  };

  const anchors = await Promise.all(Array.prototype.map.call(dataTable.querySelectorAll('tbody tr:not([hidden])'), async (tr) => {
    const a = tr.querySelector('a[href]');
    if (a) { await loadAnchorMetadata(a); }
    return a;
  }));

  const medias = [];
  for (const a of anchors) {
    if (!a) { continue; }

    const type = a.dataset.type;
    switch (type) {
      case 'image':
        addImage(a, type);
        break;
      case 'audio':
        medias.push(addAudio(a, type).querySelector('audio'));
        break;
      case 'video':
        medias.push(addVideo(a, type).querySelector('video'));
        break;
      default:
        addAnchor(a, type);
        break;
    }
  }
  preloadMediaMetadata(medias, options); // async

  dataViewer.parentNode.replaceChild(wrapper, dataViewer);
  dataViewer = wrapper;
}

async function viewerList(options = {}) {
  document.getElementById('tools').disabled = true;
  document.getElementById('command').disabled = true;

  const wrapper = document.createElement('div');
  wrapper.id = "img-list-view";

  const addFigure = (type) => {
    const figure = wrapper.appendChild(document.createElement('figure'));
    figure.classList.add(type);
    return figure;
  };

  const addAnchor = (a, type) => {
    const href = a.dataset.href || a.href;

    const figure = addFigure(type);

    const anchor = figure.appendChild(document.createElement('a'));
    anchor.href = href;
    anchor.target = "_blank";
    anchor.textContent = a.textContent;
    anchor.className = 'icon ' + type;

    return figure;
  };

  const addImage = (a, type) => {
    const href = a.dataset.href || a.href;

    const figure = addFigure(type);

    const div = figure.appendChild(document.createElement('div'));

    const img = div.appendChild(document.createElement('img'));
    img.src = href;
    img.alt = img.title = a.textContent;

    const anchor = figure.appendChild(document.createElement('a'));
    anchor.href = href;
    anchor.target = "_blank";
    anchor.textContent = a.textContent;

    return figure;
  };

  const addAudio = (a, type) => {
    const href = a.dataset.href || a.href;

    const figure = addFigure(type);

    const div = figure.appendChild(document.createElement('div'));

    const audio = div.appendChild(document.createElement('audio'));
    audio.src = href;
    audio.controls = true;
    audio.preload = 'none';
    audio.title = a.textContent;

    const anchor = figure.appendChild(document.createElement('a'));
    anchor.href = href;
    anchor.target = "_blank";
    anchor.textContent = a.textContent;

    return figure;
  };

  const addVideo = (a, type) => {
    const href = a.dataset.href || a.href;

    const figure = addFigure(type);

    const div = figure.appendChild(document.createElement('div'));

    const video = div.appendChild(document.createElement('video'));
    video.src = href;
    video.controls = true;
    video.preload = 'none';
    video.title = a.textContent;

    const anchor = figure.appendChild(document.createElement('a'));
    anchor.href = href;
    anchor.target = "_blank";
    anchor.textContent = a.textContent;

    return figure;
  };

  const anchors = await Promise.all(Array.prototype.map.call(dataTable.querySelectorAll('tbody tr:not([hidden])'), async (tr) => {
    const a = tr.querySelector('a[href]');
    if (a) { await loadAnchorMetadata(a); }
    return a;
  }));

  const medias = [];
  for (const a of anchors) {
    if (!a) { continue; }

    const type = a.dataset.type;
    switch (type) {
      case 'image':
        addImage(a, type);
        break;
      case 'audio':
        medias.push(addAudio(a, type).querySelector('audio'));
        break;
      case 'video':
        medias.push(addVideo(a, type).querySelector('video'));
        break;
      default:
        addAnchor(a, type);
        break;
    }
  }
  preloadMediaMetadata(medias, options); // async

  dataViewer.parentNode.replaceChild(wrapper, dataViewer);
  dataViewer = wrapper;
}

async function expandTableRow(tr, deep = false) {
  if (!tr.classList.contains("dir")) { return; }

  const a = tr.querySelector('a[href]');
  if (!a) { return; }

  const tdDir = tr.querySelector('td');
  const dirSortKey = tdDir.getAttribute("data-sort") + "/";
  const dirTitle = tdDir.querySelector('a').title + "/";
  const hidden = tr.hidden;

  tr.setAttribute("data-expanded", "");

  try {
    const doc = (await utils.xhr({
      url: a.href,
      responseType: 'document',
    })).response;
    const trNext = tr.nextSibling;
    for (const trNew of doc.querySelectorAll('#data-table tbody tr')) {
      const anchor = trNew.querySelector('a[href]');
      if (!anchor) { continue; }

      trNew.hidden = hidden;

      const tdDir = trNew.querySelector('td');
      tdDir.setAttribute("data-sort", dirSortKey + tdDir.getAttribute("data-sort"));
      tdDir.querySelector('a').title = dirTitle + tdDir.querySelector('a').title;

      anchor.href = anchor.href;

      tr.parentNode.insertBefore(trNew, trNext);

      if (deep) {
        expandTableRow(trNew, deep);
      }
    }
  } catch (ex) {
    console.error(ex);
  }
}

async function preloadMediaMetadata(medias, {
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
}

function onViewerChange(event) {
  viewerApply();
}

function onToolsChange(event) {
  event.preventDefault();
  const command = event.target.value;
  event.target.value = '';

  const func = onToolsChange.commands[command];
  func();
}

onToolsChange.commands = {
  'select-all': function selectAll() {
    for (const tr of document.querySelectorAll('#data-table tbody tr')) {
      highlightElem(tr, true);
    }
  },

  'deselect-all': function deselectAll() {
    for (const tr of document.querySelectorAll('#data-table tbody tr')) {
      highlightElem(tr, false);
    }
  },

  'expand-all': async function expandAll() {
    for (const tr of document.querySelectorAll('#data-table tbody tr:not([data-expanded])')) {
      await expandTableRow(tr, true);
    }
  },

  'filter': function filter() {
    const kw = prompt('Filter with the keyword (string or "/pattern/flags" for regex):');
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
    for (const tr of document.querySelectorAll('#data-table tbody tr:not([hidden])')) {
      const anchor = tr.querySelector('a[href]');
      regex.lastIndex = 0;
      if (!regex.test(anchor.textContent)) {
        tr.hidden = true;
      }
    }
  },

  'filter-clear': function filterClear() {
    for (const tr of document.querySelectorAll('#data-table tbody tr[hidden]')) {
      tr.hidden = false;
    }
  },
};

function onCommandFocus(event) {
  const cmdElem = document.getElementById('command');
  const selectedEntries = document.querySelectorAll('#data-table .highlight');

  switch (selectedEntries.length) {
    case 0: {
      cmdElem.querySelector('[value="mkdir"]').hidden = false;
      cmdElem.querySelector('[value="mkzip"]').hidden = false;
      cmdElem.querySelector('[value="mkfile"]').hidden = false;
      cmdElem.querySelector('[value="upload"]').hidden = false;
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
      const isHtml = /\.(?:x?html?|xht)$/i.test(elem.querySelector('a[href]').href);
      cmdElem.querySelector('[value="mkdir"]').hidden = true;
      cmdElem.querySelector('[value="mkzip"]').hidden = true;
      cmdElem.querySelector('[value="mkfile"]').hidden = true;
      cmdElem.querySelector('[value="upload"]').hidden = true;
      cmdElem.querySelector('[value="exec"]').hidden = false;
      cmdElem.querySelector('[value="browse"]').hidden = false;
      cmdElem.querySelector('[value="download"]').hidden = false;
      cmdElem.querySelector('[value="move"]').hidden = false;
      cmdElem.querySelector('[value="copy"]').hidden = false;
      cmdElem.querySelector('[value="link"]').hidden = false;
      cmdElem.querySelector('[value="delete"]').hidden = false;
      if (elem.classList.contains('link')) {
        cmdElem.querySelector('[value="source"]').hidden = false;
        cmdElem.querySelector('[value="edit"]').hidden = true;
        cmdElem.querySelector('[value="editx"]').hidden = true;
      } else if (elem.classList.contains('file')) {
        cmdElem.querySelector('[value="source"]').hidden = false;
        cmdElem.querySelector('[value="edit"]').hidden = false;
        cmdElem.querySelector('[value="editx"]').hidden = !isHtml;
      } else if (elem.classList.contains('dir')) {
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

    default: {
      return onCommandRun({cmd: command});
      break;
    }
  }
}

function onCommandRun(detail) {
  const command = detail.cmd;
  const func = onCommandRun.commands[command];
  const selectedEntries = document.querySelectorAll('#data-table .highlight');
  func(selectedEntries, detail);
}

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
      for (const elem of selectedEntries) {
        const entry = elem.querySelector('a[title]').getAttribute('title');
        u.searchParams.append('i', entry);
      }
      location.href = u.href;
    }
  },

  async exec(selectedEntries) {
    const target = selectedEntries[0].querySelector('a[href]').href;
    try {
      await utils.wsb({
        url: target + '?a=exec&f=json',
        responseType: 'json',
        method: "GET",
      });
    } catch (ex) {
      const base = document.getElementById('data-table').getAttribute('data-base');
      const oldPath = decodeURIComponent(new URL(target).pathname).slice(base.length);
      alert(`Unable to run "${oldPath}": ${ex.message}`);
    }
  },

  async browse(selectedEntries) {
    const target = selectedEntries[0].querySelector('a[href]').href;
    try {
      await utils.wsb({
        url: target + '?a=browse&f=json',
        responseType: 'json',
        method: "GET",
      });
    } catch (ex) {
      const base = document.getElementById('data-table').getAttribute('data-base');
      const oldPath = decodeURIComponent(new URL(target).pathname).slice(base.length);
      alert(`Unable to browse "${oldPath}": ${ex.message}`);
    }
  },

  async mkdir(selectedEntries) {
    const newFolderName = prompt('Input a name:', 'new-folder');
    if (!newFolderName) {
      return;
    }

    const target = utils.getTargetUrl(location.href) + encodeURIComponent(newFolderName);
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
      alert(`Unable to create directory "${newFolderName}": ${ex.message}`);
      return;
    }
    location.reload();
  },

  async mkzip(selectedEntries) {
    const newFileName = prompt('Input a name:', 'new-archive.zip');
    if (!newFileName) {
      return;
    }

    const target = utils.getTargetUrl(location.href) + encodeURIComponent(newFileName);
    try {
      const formData = new FormData();
      formData.append('token', await utils.acquireToken(target));

      await utils.wsb({
        url: target + '?a=mkzip&f=json',
        responseType: 'json',
        method: "POST",
        formData: formData,
      });
    } catch (ex) {
      alert(`Unable to create ZIP "${newFileName}": ${ex.message}`);
      return;
    }
    location.reload();
  },

  async mkfile(selectedEntries) {
    const newFileName = prompt('Input a name:', 'new-file.txt');
    if (!newFileName) {
      return;
    }

    const target = utils.getTargetUrl(location.href) + encodeURIComponent(newFileName);
    location.href = target + '?a=edit&back=' + encodeURIComponent(location.href);
  },

  async edit(selectedEntries) {
    const target = selectedEntries[0].querySelector('a[href]').href;
    location.href = target + '?a=edit&back=' + encodeURIComponent(location.href);
  },

  async editx(selectedEntries) {
    const target = selectedEntries[0].querySelector('a[href]').href;
    location.href = target + '?a=editx&back=' + encodeURIComponent(location.href);
  },

  async upload(selectedEntries, {files: entries}) {
    const base = document.getElementById('data-table').getAttribute('data-base');
    const dir = document.getElementById('data-table').getAttribute('data-path');
    const errors = [];
    for (const file of entries) {
      const newPath = dir + file.name;
      const target = location.origin + (base + newPath).split('/').map(x => encodeURIComponent(x)).join('/');
      try {
        const formData = new FormData();
        formData.append('token', await utils.acquireToken(dir));
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
  },

  async move(selectedEntries) {
    const moveEntry = async (target, oldPath, newPath) => {
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

    const base = document.getElementById('data-table').getAttribute('data-base');
    const dir = document.getElementById('data-table').getAttribute('data-path');
    if (selectedEntries.length === 1) {
      const target = selectedEntries[0].querySelector('a[href]').href;
      const oldPath = decodeURIComponent(new URL(target).pathname).slice(base.length);
      const newPath = prompt('Input the new path:', oldPath);
      if (!newPath) {
        return;
      }

      try {
        await moveEntry(target, oldPath, newPath);
      } catch (ex) {
        alert(`Unable to move "${oldPath}" => "${newPath}": ${ex.message}`);
        return;
      }
    } else {
      let newDir = prompt('Move to the path:', dir);
      if (!newDir) {
        return;
      }

      newDir = newDir.replace(/\/+$/, '') + '/';

      const entries = Array.prototype.map.call(selectedEntries, entry => {
        const target = entry.querySelector('a[href]').href;
        const oldPath = decodeURIComponent(new URL(target).pathname).slice(base.length);
        const newPath = newDir + oldPath.match(/[^\/]+\/?$/)[0];
        return {target, oldPath, newPath};
      });
      const errors = [];
      for (const {target, oldPath, newPath} of entries.sort(onCommandRun.sortEntries).reverse()) {
        try {
          await moveEntry(target, oldPath, newPath);
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
    const copyEntry = async (target, oldPath, newPath) => {
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

    const base = document.getElementById('data-table').getAttribute('data-base');
    const dir = document.getElementById('data-table').getAttribute('data-path');
    if (selectedEntries.length === 1) {
      const target = selectedEntries[0].querySelector('a[href]').href;
      const oldPath = decodeURIComponent(new URL(target).pathname).slice(base.length);
      const newPath = prompt('Input the new path:', oldPath);
      if (!newPath) {
        return;
      }

      try {
        await copyEntry(target, oldPath, newPath);
      } catch (ex) {
        alert(`Unable to copy "${oldPath}" => "${newPath}": ${ex.message}`);
        return;
      }
    } else {
      let newDir = prompt('Copy to the path:', dir);
      if (!newDir) {
        return;
      }

      newDir = newDir.replace(/\/+$/, '') + '/';

      const entries = Array.prototype.map.call(selectedEntries, entry => {
        const target = entry.querySelector('a[href]').href;
        const oldPath = decodeURIComponent(new URL(target).pathname).slice(base.length);
        const newPath = newDir + oldPath.match(/[^\/]+\/?$/)[0];
        return {target, oldPath, newPath};
      });
      const errors = [];
      for (const {target, oldPath, newPath} of entries.sort(onCommandRun.sortEntries).reverse()) {
        try {
          await copyEntry(target, oldPath, newPath);
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

    const linkEntry = async (source, target, oldPath, newPath) => {
      const url = getRelativePath(oldPath, newPath).replace(/[%#?]+/g, x => encodeURIComponent(x));
      const content = '<meta charset="UTF-8"><meta http-equiv="refresh" content="0; url=' + url + '">';

      const formData = new FormData();
      formData.append('token', await utils.acquireToken(source));
      // encode the text as ISO-8859-1 (byte string) so that it's 100% recovered
      formData.append('text', unescape(encodeURIComponent(content)));

      await utils.wsb({
        url: target + '?a=save&f=json',
        responseType: 'json',
        method: "POST",
        formData: formData,
      });
    };

    const base = document.getElementById('data-table').getAttribute('data-base');
    const dir = document.getElementById('data-table').getAttribute('data-path');
    if (selectedEntries.length === 1) {
      const source = selectedEntries[0].querySelector('a[href]').href;
      const oldPath = decodeURIComponent(new URL(source).pathname).slice(base.length);
      let newPath = oldPath.replace(/\/$/, '') + '.lnk.htm';
      newPath = prompt('Input the new path:', newPath);
      if (!newPath) {
        return;
      }

      const target = location.origin + (base + newPath).split('/').map(x => encodeURIComponent(x)).join('/');

      try {
        await linkEntry(source, target, oldPath, newPath);
      } catch (ex) {
        alert(`Unable to create link "${oldPath}" => "${newPath}": ${ex.message}`);
        return;
      }
    } else {
      let newDir = prompt('Create links at the path:', dir);
      if (!newDir) {
        return;
      }

      newDir = newDir.replace(/\/+$/, '') + '/';
      const entries = Array.prototype.map.call(selectedEntries, entry => {
        const source = entry.querySelector('a[href]').href;
        const oldPath = decodeURIComponent(new URL(source).pathname).slice(base.length);
        const newPath = newDir + oldPath.match(/[^\/]+\/?$/)[0].replace(/\/$/, '') + '.lnk.htm';
        const target = location.origin + (base + newPath).split('/').map(x => encodeURIComponent(x)).join('/');
        return {source, target, oldPath, newPath};
      }).sort(onCommandRun.sortEntries).reverse();
      const errors = [];
      for (const {source, target, oldPath, newPath} of entries) {
        try {
          await linkEntry(source, target, oldPath, newPath);
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
    const base = document.getElementById('data-table').getAttribute('data-base');
    const entries = Array.prototype.map.call(selectedEntries, entry => {
      const target = entry.querySelector('a[href]').href;
      const oldPath = decodeURIComponent(new URL(target).pathname).slice(base.length);
      return {target, oldPath};
    });
    const errors = [];
    for (const {target, oldPath} of entries.sort(onCommandRun.sortEntries).reverse()) {
      try {
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
