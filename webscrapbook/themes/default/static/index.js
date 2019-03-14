/**
 * Support ES3 for sorting.
 *
 * Viewer and command may require ES6 for enhanced functionalities.
 */
var dataTable;
var dataViewer;

document.addEventListener("DOMContentLoaded", function (event) {
  document.getElementById("panel").hidden = false;

  /* Init sort */
  dataViewer = dataTable = document.getElementById("data-table");
  var head_row = dataTable.tHead.rows[0];
  for (var i = 0, I = head_row.cells.length; i < I; i++) {
    var elem = head_row.cells[i];
    elem.setAttribute("data-orderby", i);
    elem.addEventListener("click", function (event) {
      orderBy(parseInt(event.currentTarget.getAttribute('data-orderby'), 10));
    }, false);
  }

  /* Data table */
  document.getElementById("data-table").tBodies[0].addEventListener("click", onDataTableClick, false);

  /* Media viewers */
  browseHtmlFolder();
  document.getElementById("viewer").addEventListener("change", viewerApply, false);

  /* Command handler */
  document.getElementById("command").addEventListener("focus", onCommandFocus, false);
  document.getElementById("command").addEventListener("change", onCommandChange, false);

  // file selector
  document.getElementById('upload-file-selector').addEventListener('change', (event) => {
    event.preventDefault();
    const evt = new CustomEvent("command", {
      detail: {
        cmd: 'upload',
        files: event.target.files,
      },
    });
    window.dispatchEvent(evt);
  });

  // command listener
  window.addEventListener("command", onCommandRun, false);
}, false);

function orderBy(column, order) {
  if (typeof order === "undefined") {
    order = (dataTable.getAttribute("data-order") == 1) ? -1 : 1;
  }

  dataTable.setAttribute("data-orderby", column);
  dataTable.setAttribute("data-order", order);

  var keyFuncForColumn = [
    function (k) { return k.toLowerCase(); },
    function (k) { return k.toLowerCase(); },
    function (k) { return parseFloat(k) || 0; },
    function (k) { return parseInt(k) || 0; }
  ];

  var tbody = dataTable.tBodies[0];
  var rows = Array.prototype.slice.call(tbody.rows);

  rows.sort(function (a, b) {
    var ka = a.cells[column].getAttribute("data-sort") || "";
    var kb = b.cells[column].getAttribute("data-sort") || "";
    ka = keyFuncForColumn[column](ka);
    kb = keyFuncForColumn[column](kb);

    if (ka < kb) {
      return -order;
    }
    if (ka > kb) {
      return order;
    }
    return 0;
  });

  for (var i = 0, I = rows.length; i < I; i++) {
    tbody.appendChild(rows[i]);
  }
}

function onDataTableClick(event) {
  var elem = event.target;
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

function browseHtmlFolder() {
  var path = document.getElementById('data-table').getAttribute('data-path');

  /* handle .htd */
  if (/\.(htd)\/?$/i.test(path)) {
    // if there's index.html, redirect to view it
    var indexAnchor = dataTable.querySelector('tr:not(.extra) a[href="index.html"]');
    if (indexAnchor) {
      location.replace(indexAnchor.href);
      return;
    }

    // otherwise, use gallery view
    document.getElementById("viewer").value = 'gallery';
    viewerApply();
  }
}

function viewerApply() {
  switch (document.getElementById("viewer").value) {
    case "gallery":
      viewerGallery();
      break;
    case "list":
      viewerList();
      break;
    case "deep":
      viewerDeepList();
      break;
    default:
      viewerDefault();
      break;
  }
}

function viewerDefault() {
  if (dataViewer === dataTable) { return; }

  dataViewer.parentNode.replaceChild(dataTable, dataViewer);
  dataViewer = dataTable;
}

function viewerGallery() {
  if (dataViewer.id === "img-gallery-view") { return; }

  var wrapper = wrapper = document.createElement('div');
  wrapper.id = "img-gallery-view";

  var deferredElems = [];

  var addImage = function (a, cls) {
    var figure = wrapper.appendChild(document.createElement('figure'));
    figure.style ='display: inline-block; margin: 0.2em; border: 0; padding: 0;';

    var anchor = figure.appendChild(document.createElement('a'));
    anchor.href = a.href;
    anchor.target = "_blank";

    var img = anchor.appendChild(document.createElement('img'));
    img.src = a.href;
    img.alt = img.title = a.textContent;
    img.style = 'margin: 0; border: 0; padding: 0; max-width: 100%; max-height: 200px;';
    if (/\s*dir\s*/.test(cls)) { img.style.backgroundColor = '#ff8'; }

    return figure;
  };

  var addVideo = function (a) {
    var figure = wrapper.appendChild(document.createElement('figure'));
    figure.style ='display: inline-block; margin: 0.2em; border: 0; padding: 0;';

    var video = figure.appendChild(document.createElement('video'));
    video.src = a.href;
    video.setAttribute("controls", "");
    video.title = a.textContent;
    video.style = 'margin: 0; border: 0; padding: 0; max-width: 100%; max-height: 200px;';

    return figure;
  };

  Array.prototype.forEach.call(dataTable.querySelectorAll('tr:not(.extra)'), function (tr) {
    var a = tr.querySelector('a[href]');
    if (!a) { return; }

    if (/\.(jpg|jpeg?|gif|png|bmp|ico|webp|svg)$/i.test(a.href)) {
      addImage(a);
    } else if (/\.(mp4|ogg|webm)$/i.test(a.href)) {
      addVideo(a);
    } else {
      deferredElems.push(addImage(a, tr.className));
    }
  });

  // move deferred elems to last
  deferredElems.forEach(function (elem) {
    wrapper.appendChild(elem);
  });

  dataViewer.parentNode.replaceChild(wrapper, dataViewer);
  dataViewer = wrapper;
}

function viewerList() {
  if (dataViewer.id === "img-list-view") { return; }

  var wrapper = document.createElement('div');
  wrapper.id = "img-list-view";

  var deferredElems = [];

  var addImage = function (a, cls) {
    var figure = wrapper.appendChild(document.createElement('figure'));
    figure.style = 'margin-left: 0; margin-right: 0;';

    var anchor = figure.appendChild(document.createElement('a'));
    anchor.href = a.href;
    anchor.target = "_blank";

    var img = anchor.appendChild(document.createElement('img'));
    img.src = a.href;
    img.alt = img.title = a.textContent;
    img.style = 'max-width: 90vw; max-height: 90vh;';
    if (/\s*dir\s*/.test(cls)) { img.style.backgroundColor = '#ff8'; }

    return figure;
  };

  var addVideo = function (a) {
    var figure = wrapper.appendChild(document.createElement('figure'));
    figure.style = 'margin-left: 0; margin-right: 0;';

    var video = figure.appendChild(document.createElement('video'));
    video.src = a.href;
    video.setAttribute("controls", "");
    video.title = a.textContent;
    video.style = 'max-width: 90vw; max-height: 90vh;';

    return figure;
  };

  Array.prototype.forEach.call(dataTable.querySelectorAll('tr:not(.extra)'), function (tr) {
    var a = tr.querySelector('a[href]');
    if (!a) { return; }

    if (/\.(jpg|jpeg?|gif|png|bmp|ico|webp|svg)$/i.test(a.href)) {
      addImage(a);
    } else if (/\.(mp4|ogg|webm)$/i.test(a.href)) {
      addVideo(a);
    } else {
      deferredElems.push(addImage(a, tr.className));
    }
  });

  // move deferred elems to last
  deferredElems.forEach(function (elem) {
    wrapper.appendChild(elem);
  });

  dataViewer.parentNode.replaceChild(wrapper, dataViewer);
  dataViewer = wrapper;
}

async function viewerDeepList() {
  const expandRow = async function (tr) {
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
      Array.prototype.forEach.call(
        doc.querySelectorAll('#data-table tr:not(.extra)'),
        row => {
          const anchor = row.querySelector('a[href]');
          if (!anchor) { return; }

          const tdDir = row.querySelector('td');
          tdDir.setAttribute("data-sort", dirSortKey + tdDir.getAttribute("data-sort"));
          tdDir.querySelector('a').title = dirTitle + tdDir.querySelector('a').title;

          anchor.href = anchor.href;

          tr.parentNode.insertBefore(row, trNext);
          expandRow(row);
        });
    } catch (ex) {
      console.error(ex);
    }
  };

  for (const tr of dataTable.querySelectorAll('tr:not(.extra):not([data-expanded])')) {
    await expandRow(tr);
  }
}

function onCommandFocus(event) {
  const cmdElem = document.getElementById('command');
  const selectedEntries = document.querySelectorAll('#data-table .highlight');

  switch (selectedEntries.length) {
    case 0: {
      cmdElem.querySelector('[value="source"]').hidden = true;
      cmdElem.querySelector('[value="exec"]').hidden = true;
      cmdElem.querySelector('[value="browse"]').hidden = true;
      cmdElem.querySelector('[value="mkdir"]').hidden = false;
      cmdElem.querySelector('[value="edit"]').hidden = false;
      cmdElem.querySelector('[value="editx"]').hidden = true;
      cmdElem.querySelector('[value="upload"]').hidden = false;
      cmdElem.querySelector('[value="move"]').hidden = true;
      cmdElem.querySelector('[value="copy"]').hidden = true;
      cmdElem.querySelector('[value="delete"]').hidden = true;

      cmdElem.querySelector('[value="edit"]').textContent = 'New File';
      break;
    }

    case 1: {
      const elem = selectedEntries[0];
      const isHtml = /\.(?:x?html?|xht)$/i.test(elem.querySelector('a[href]').href);
      if (elem.classList.contains('link')) {
        cmdElem.querySelector('[value="source"]').hidden = false;
        cmdElem.querySelector('[value="exec"]').hidden = false;
        cmdElem.querySelector('[value="browse"]').hidden = false;
        cmdElem.querySelector('[value="mkdir"]').hidden = true;
        cmdElem.querySelector('[value="edit"]').hidden = true;
        cmdElem.querySelector('[value="editx"]').hidden = true;
        cmdElem.querySelector('[value="upload"]').hidden = true;
        cmdElem.querySelector('[value="move"]').hidden = false;
        cmdElem.querySelector('[value="copy"]').hidden = false;
        cmdElem.querySelector('[value="delete"]').hidden = false;
      } else if (elem.classList.contains('file')) {
        cmdElem.querySelector('[value="source"]').hidden = false;
        cmdElem.querySelector('[value="exec"]').hidden = false;
        cmdElem.querySelector('[value="browse"]').hidden = false;
        cmdElem.querySelector('[value="mkdir"]').hidden = true;
        cmdElem.querySelector('[value="edit"]').hidden = false;
        cmdElem.querySelector('[value="editx"]').hidden = !isHtml;
        cmdElem.querySelector('[value="upload"]').hidden = true;
        cmdElem.querySelector('[value="move"]').hidden = false;
        cmdElem.querySelector('[value="copy"]').hidden = false;
        cmdElem.querySelector('[value="delete"]').hidden = false;

        cmdElem.querySelector('[value="edit"]').textContent = 'Edit';
      } else if (elem.classList.contains('dir')) {
        cmdElem.querySelector('[value="source"]').hidden = true;
        cmdElem.querySelector('[value="exec"]').hidden = false;
        cmdElem.querySelector('[value="browse"]').hidden = false;
        cmdElem.querySelector('[value="mkdir"]').hidden = true;
        cmdElem.querySelector('[value="edit"]').hidden = true;
        cmdElem.querySelector('[value="editx"]').hidden = true;
        cmdElem.querySelector('[value="upload"]').hidden = true;
        cmdElem.querySelector('[value="move"]').hidden = false;
        cmdElem.querySelector('[value="copy"]').hidden = false;
        cmdElem.querySelector('[value="delete"]').hidden = false;
      }
      break;
    }

    default: { // multiple
      cmdElem.querySelector('[value="source"]').hidden = true;
      cmdElem.querySelector('[value="exec"]').hidden = true;
      cmdElem.querySelector('[value="browse"]').hidden = true;
      cmdElem.querySelector('[value="mkdir"]').hidden = true;
      cmdElem.querySelector('[value="edit"]').hidden = true;
      cmdElem.querySelector('[value="editx"]').hidden = true;
      cmdElem.querySelector('[value="upload"]').hidden = true;
      cmdElem.querySelector('[value="move"]').hidden = false;
      cmdElem.querySelector('[value="copy"]').hidden = false;
      cmdElem.querySelector('[value="delete"]').hidden = false;
      break;
    }
  }
}

async function onCommandChange(event) {
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
      const evt = new CustomEvent("command", {
        detail: {
          cmd: command,
        },
      });
      window.dispatchEvent(evt);
    }
  }
}

async function onCommandRun(event) {
  const command = event.detail.cmd;
  const selectedEntries = document.querySelectorAll('#data-table .highlight');

  switch (command) {
    case 'source': {
      const target = selectedEntries[0].querySelector('a[href]').href;
      location.href = target + '?a=source';
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
      const newFolderName = prompt('Input a name:', 'New Folder');
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

    case 'edit': {
      if (selectedEntries.length) {
        const target = selectedEntries[0].querySelector('a[href]').href;
        location.href = target + '?a=edit&back=' + encodeURIComponent(location.href);
      } else {
        const newFileName = prompt('Input a name:', 'New File');
        if (!newFileName) {
          break;
        }

        const target = utils.getTargetUrl(location.href) + encodeURIComponent(newFileName);
        location.href = target + '?a=edit&back=' + encodeURIComponent(location.href);
      }
      break;
    }

    case 'editx': {
      const target = selectedEntries[0].querySelector('a[href]').href;
      location.href = target + '?a=editx&back=' + encodeURIComponent(location.href);
      break;
    }

    case 'upload': {
      const dir = utils.getTargetUrl(location.href);

      for (const file of event.detail.files) {
        const target = dir + file.name;
        try {
          const formData = new FormData();
          formData.append('token', await utils.acquireToken(dir));
          formData.append('upload', file);

          let xhr = await utils.wsb({
            url: target + '?a=upload&f=json',
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
        const newPath = prompt('Input the new path:', dir + '/' + decodeURIComponent(target));
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
        const newPath = prompt('Input the new path:', dir + '/' + decodeURIComponent(target));
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
