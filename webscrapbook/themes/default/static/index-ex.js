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
  if (/\.(jpg|jpeg?|gif|png|bmp|ico|webp|svg)$/i.test(url)) {
    return 'image';
  } else if (/\.(mp4|ogv|ogx|ogg|webm)$/i.test(url)) {
    return 'video';
  } else if (/\.(wav|mp3|oga|weba)$/i.test(url)) {
    return 'audio';
  } else {
    return 'unknown';
  }
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
    case "list":
      viewerList();
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

async function viewerGallery() {
  if (dataViewer.id === "img-gallery-view") { return; }

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
    const figure = addFigure(type);

    const anchor = figure.appendChild(document.createElement('a'));
    anchor.href = a.href;
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
    const figure = addFigure(type);

    const anchor = figure.appendChild(document.createElement('a'));
    anchor.href = a.href;
    anchor.target = "_blank";
    anchor.title = a.textContent;

    const div = anchor.appendChild(document.createElement('div'));

    const img = div.appendChild(document.createElement('img'));
    img.src = a.href;
    img.alt = a.textContent;

    const span = anchor.appendChild(document.createElement('span'));
    span.textContent = a.textContent;

    return figure;
  };

  const addAudio = (a, type) => {
    const figure = addFigure(type);

    const div = figure.appendChild(document.createElement('div'));

    const audio = div.appendChild(document.createElement('audio'));
    audio.src = a.href;
    audio.setAttribute("controls", "");

    const anchor = figure.appendChild(document.createElement('a'));
    anchor.href = a.href;
    anchor.target = "_blank";
    anchor.title = a.textContent;

    const span = anchor.appendChild(document.createElement('span'));
    span.textContent = a.textContent;

    return figure;
  };

  const addVideo = (a, type) => {
    const figure = addFigure(type);

    const div = figure.appendChild(document.createElement('div'));

    const video = div.appendChild(document.createElement('video'));
    video.src = a.href;
    video.setAttribute("controls", "");

    const anchor = figure.appendChild(document.createElement('a'));
    anchor.href = a.href;
    anchor.target = "_blank";
    anchor.title = a.textContent;

    const span = anchor.appendChild(document.createElement('span'));
    span.textContent = a.textContent;

    return figure;
  };

  const tasks = await Promise.all(Array.prototype.map.call(dataTable.querySelectorAll('tbody tr'), (tr) => {
    let type = tr.classList.contains('dir') ? 'dir' : 'unknown';
    const a = tr.querySelector('a[href]');
    if (!a) { return {a, type}; }

    if (type === 'dir') { return {a, type}; }

    type = getTypeFromUrl(a.href);
    if (type !== 'unknown') { return {a, type}; }

    return fetch(a.href, {method: 'HEAD'}).then(r => {
      type = getTypeFromUrl(r.url);
      if (type !== 'unknown') { return {a, type}; }
      type = 'file';
      return {a, type};
    }).catch(ex => {
      type = 'link';
      return {a, type};
    });
  }));

  for (const {a, type} of tasks) {
    if (!a) { continue; }

    switch (type) {
      case 'image':
        addImage(a, type);
        break;
      case 'audio':
        addAudio(a, type);
        break;
      case 'video':
        addVideo(a, type);
        break;
      default:
        addAnchor(a, type);
        break;
    }
  }

  dataViewer.parentNode.replaceChild(wrapper, dataViewer);
  dataViewer = wrapper;
}

async function viewerList() {
  if (dataViewer.id === "img-list-view") { return; }

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
    const figure = addFigure(type);

    const anchor = figure.appendChild(document.createElement('a'));
    anchor.href = a.href;
    anchor.target = "_blank";
    anchor.textContent = a.textContent;
    anchor.className = 'icon ' + type;

    return figure;
  };

  const addImage = (a, type) => {
    const figure = addFigure(type);

    const div = figure.appendChild(document.createElement('div'));

    const img = div.appendChild(document.createElement('img'));
    img.src = a.href;
    img.alt = img.title = a.textContent;

    const anchor = figure.appendChild(document.createElement('a'));
    anchor.href = a.href;
    anchor.target = "_blank";
    anchor.textContent = a.textContent;

    return figure;
  };

  const addAudio = (a, type) => {
    const figure = addFigure(type);

    const div = figure.appendChild(document.createElement('div'));

    const audio = div.appendChild(document.createElement('audio'));
    audio.src = a.href;
    audio.setAttribute("controls", "");
    audio.title = a.textContent;

    const anchor = figure.appendChild(document.createElement('a'));
    anchor.href = a.href;
    anchor.target = "_blank";
    anchor.textContent = a.textContent;

    return figure;
  };

  const addVideo = (a, type) => {
    const figure = addFigure(type);

    const div = figure.appendChild(document.createElement('div'));

    const video = div.appendChild(document.createElement('video'));
    video.src = a.href;
    video.setAttribute("controls", "");
    video.title = a.textContent;

    const anchor = figure.appendChild(document.createElement('a'));
    anchor.href = a.href;
    anchor.target = "_blank";
    anchor.textContent = a.textContent;

    return figure;
  };

  const tasks = await Promise.all(Array.prototype.map.call(dataTable.querySelectorAll('tbody tr'), (tr) => {
    let type = tr.classList.contains('dir') ? 'dir' : 'unknown';
    const a = tr.querySelector('a[href]');
    if (!a) { return {a, type}; }

    if (type === 'dir') { return {a, type}; }

    type = getTypeFromUrl(a.href);
    if (type !== 'unknown') { return {a, type}; }

    return fetch(a.href, {method: 'HEAD'}).then(r => {
      type = getTypeFromUrl(r.url);
      if (type !== 'unknown') { return {a, type}; }
      type = 'file';
      return {a, type};
    }).catch(ex => {
      type = 'link';
      return {a, type};
    });
  }));

  for (const {a, type} of tasks) {
    if (!a) { continue; }

    switch (type) {
      case 'image':
        addImage(a, type);
        break;
      case 'audio':
        addAudio(a, type);
        break;
      case 'video':
        addVideo(a, type);
        break;
      default:
        addAnchor(a, type);
        break;
    }
  }

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

function onViewerChange(event) {
  viewerApply();
}

async function onToolsChange(event) {
  event.preventDefault();
  const command = event.target.value;
  event.target.value = '';

  switch (command) {
    case 'select-all': {
      for (const tr of document.querySelectorAll('#data-table tbody tr')) {
        highlightElem(tr, true);
      }
      break;
    }
    case 'deselect-all': {
      for (const tr of document.querySelectorAll('#data-table tbody tr')) {
        highlightElem(tr, false);
      }
      break;
    }
    case 'expand-all': {
      for (const tr of document.querySelectorAll('#data-table tbody tr:not([data-expanded])')) {
        await expandTableRow(tr, true);
      }
      break;
    }
  }
}

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

async function onCommandRun(detail) {
  const command = detail.cmd;
  const selectedEntries = document.querySelectorAll('#data-table .highlight');

  switch (command) {
    case 'source': {
      const target = selectedEntries[0].querySelector('a[href]').href;
      location.href = target + '?a=source';
      break;
    }

    case 'download': {
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
      break;
    }

    case 'exec': {
      const target = selectedEntries[0].querySelector('a[href]').href;
      try {
        let xhr = await utils.wsb({
          url: target + '?a=exec&f=json',
          responseType: 'json',
          method: "GET",
        });
      } catch (ex) {
        alert(`Unable to run "${target}": ${ex.message}`);
      }
      break;
    }

    case 'browse': {
      const target = selectedEntries[0].querySelector('a[href]').href;
      try {
        let xhr = await utils.wsb({
          url: target + '?a=browse&f=json',
          responseType: 'json',
          method: "GET",
        });
      } catch (ex) {
        alert(`Unable to browse "${target}": ${ex.message}`);
      }
      break;
    }

    case 'mkdir': {
      const newFolderName = prompt('Input a name:', 'new-folder');
      if (!newFolderName) {
        break;
      }

      const target = utils.getTargetUrl(location.href) + encodeURIComponent(newFolderName);
      try {
        const formData = new FormData();
        formData.append('token', await utils.acquireToken(target));

        const xhr = await utils.wsb({
          url: target + '?a=mkdir&f=json',
          responseType: 'json',
          method: "POST",
          formData: formData,
        });
      } catch (ex) {
        alert(`Unable to create directory "${newFolderName}": ${ex.message}`);
        break;
      }
      location.reload();
      break;
    }

    case 'mkzip': {
      const newFileName = prompt('Input a name:', 'new-archive.zip');
      if (!newFileName) {
        break;
      }

      const target = utils.getTargetUrl(location.href) + encodeURIComponent(newFileName);
      try {
        const formData = new FormData();
        formData.append('token', await utils.acquireToken(target));

        const xhr = await utils.wsb({
          url: target + '?a=mkzip&f=json',
          responseType: 'json',
          method: "POST",
          formData: formData,
        });
      } catch (ex) {
        alert(`Unable to create ZIP "${newFileName}": ${ex.message}`);
        break;
      }
      location.reload();
      break;
    }

    case 'mkfile': {
      const newFileName = prompt('Input a name:', 'new-file.txt');
      if (!newFileName) {
        break;
      }

      const target = utils.getTargetUrl(location.href) + encodeURIComponent(newFileName);
      location.href = target + '?a=edit&back=' + encodeURIComponent(location.href);
      break;
    }

    case 'edit': {
      const target = selectedEntries[0].querySelector('a[href]').href;
      location.href = target + '?a=edit&back=' + encodeURIComponent(location.href);
      break;
    }

    case 'editx': {
      const target = selectedEntries[0].querySelector('a[href]').href;
      location.href = target + '?a=editx&back=' + encodeURIComponent(location.href);
      break;
    }

    case 'upload': {
      const dir = utils.getTargetUrl(location.href);

      for (const file of detail.files) {
        const target = dir + file.name;
        try {
          const formData = new FormData();
          formData.append('token', await utils.acquireToken(dir));
          formData.append('upload', file);

          let xhr = await utils.wsb({
            url: target + '?a=save&f=json',
            responseType: 'json',
            method: "POST",
            formData: formData,
          });
        } catch (ex) {
          alert(`Unable to upload to "${target}": ${ex.message}`);
        }
      }
      location.reload();
      break;
    }

    case 'move': {
      const dir = document.getElementById('data-table').getAttribute('data-path');
      if (selectedEntries.length === 1) {
        const target = selectedEntries[0].querySelector('a[href]').getAttribute('href');
        const newPath = prompt('Input the new path:', dir + decodeURIComponent(target));
        if (!newPath) {
          break;
        }

        try {
          const formData = new FormData();
          formData.append('token', await utils.acquireToken(target));
          formData.append('target', newPath);

          let xhr = await utils.wsb({
            url: target + '?a=move&f=json',
            responseType: 'json',
            method: "POST",
            formData: formData,
          });
        } catch (ex) {
          alert(`Unable to move "${target}": ${ex.message}`);
          break;
        }
      } else {
        let newDir = prompt('Move to the path:', dir);
        if (!newDir) {
          break;
        }

        newDir = newDir.replace(/\/+$/, '') + '/';
        for (const entry of selectedEntries) {
          const target = entry.querySelector('a[href]').getAttribute('href');
          const newPath = newDir + decodeURIComponent(target);

          try {
            const formData = new FormData();
            formData.append('token', await utils.acquireToken(target));
            formData.append('target', newPath);

            let xhr = await utils.wsb({
              url: target + '?a=move&f=json',
              responseType: 'json',
              method: "POST",
              formData: formData,
            });
          } catch (ex) {
            alert(`Unable to move "${target}": ${ex.message}`);
            break;
          }
        }
      }
      location.reload();
      break;
    }

    case 'copy': {
      const dir = document.getElementById('data-table').getAttribute('data-path');
      if (selectedEntries.length === 1) {
        const target = selectedEntries[0].querySelector('a[href]').getAttribute('href');
        const newPath = prompt('Input the new path:', dir + decodeURIComponent(target));
        if (!newPath) {
          break;
        }

        try {
          const formData = new FormData();
          formData.append('token', await utils.acquireToken(target));
          formData.append('target', newPath);

          let xhr = await utils.wsb({
            url: target + '?a=copy&f=json',
            responseType: 'json',
            method: "POST",
            formData: formData,
          });
        } catch (ex) {
          alert(`Unable to copy "${target}": ${ex.message}`);
          break;
        }
      } else {
        let newDir = prompt('Copy to the path:', dir);
        if (!newDir) {
          break;
        }

        newDir = newDir.replace(/\/+$/, '') + '/';
        for (const entry of selectedEntries) {
          const target = entry.querySelector('a[href]').getAttribute('href');
          const newPath = newDir + decodeURIComponent(target);

          try {
            const formData = new FormData();
            formData.append('token', await utils.acquireToken(target));
            formData.append('target', newPath);

            let xhr = await utils.wsb({
              url: target + '?a=copy&f=json',
              responseType: 'json',
              method: "POST",
              formData: formData,
            });
          } catch (ex) {
            alert(`Unable to copy "${target}": ${ex.message}`);
            break;
          }
        }
      }
      location.reload();
      break;
    }

    case 'link': {
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

      const base = document.getElementById('data-table').getAttribute('data-base');
      const dir = document.getElementById('data-table').getAttribute('data-path');
      if (selectedEntries.length === 1) {
        const source = selectedEntries[0].querySelector('a[href]').getAttribute('href');
        const newPath = prompt('Input the new path:', dir + decodeURIComponent(source.replace(/\/$/, '')) + '.lnk.htm');
        if (!newPath) {
          break;
        }

        const target = (base + newPath).split('/').map(x => encodeURIComponent(x)).join('/');

        try {
          const url = getRelativePath(dir + decodeURIComponent(source), newPath).replace(/[%#?]+/g, x => encodeURIComponent(x));
          const content = '<meta charset="UTF-8"><meta http-equiv="refresh" content="0; url=' + url + '">';

          const formData = new FormData();
          formData.append('token', await utils.acquireToken(source));
          // encode the text as ISO-8859-1 (byte string) so that it's 100% recovered
          formData.append('text', unescape(encodeURIComponent(content)));

          let xhr = await utils.wsb({
            url: target + '?a=save&f=json',
            responseType: 'json',
            method: "POST",
            formData: formData,
          });
        } catch (ex) {
          alert(`Unable to create link at "${target}": ${ex.message}`);
        }
      } else {
        let newDir = prompt('Create links at the path:', dir);
        if (!newDir) {
          break;
        }

        newDir = newDir.replace(/\/+$/, '') + '/';
        for (const entry of selectedEntries) {
          const source = entry.querySelector('a[href]').getAttribute('href');
          const newPath = newDir + decodeURIComponent(source.replace(/\/$/, '')) + '.lnk.htm';
          const target = (base + newPath).split('/').map(x => encodeURIComponent(x)).join('/');

          try {
            const url = getRelativePath(dir + decodeURIComponent(source), newPath).replace(/[%#?]+/g, x => encodeURIComponent(x));
            const content = '<meta charset="UTF-8"><meta http-equiv="refresh" content="0; url=' + url + '">';

            const formData = new FormData();
            formData.append('token', await utils.acquireToken(source));
            // encode the text as ISO-8859-1 (byte string) so that it's 100% recovered
            formData.append('text', unescape(encodeURIComponent(content)));

            let xhr = await utils.wsb({
              url: target + '?a=save&f=json',
              responseType: 'json',
              method: "POST",
              formData: formData,
            });
          } catch (ex) {
            alert(`Unable to create link at "${target}": ${ex.message}`);
            break;
          }
        }
      }
      location.reload();
      break;
    }

    case 'delete': {
      for (const entry of selectedEntries) {
        const target = entry.querySelector('a[href]').href;
        try {
          const formData = new FormData();
          formData.append('token', await utils.acquireToken(target));

          const xhr = await utils.wsb({
            url: target + '?a=delete&f=json',
            responseType: 'json',
            method: "POST",
            formData: formData,
          });
        } catch (ex) {
          alert(`Unable to delete "${target}": ${ex.message}`);
        }
      }
      location.reload();
      break;
    }
  }
}

function onUploadFileChange(event) {
  event.preventDefault();
  return onCommandRun({cmd: 'upload', files: event.target.files});
}
