window.addEventListener("load", async (event) => {
  flattenFrames(window.frames[0]).forEach(frame => {
    frame.document.designMode = "on";
  });

  document.getElementById("pinned").addEventListener("click", (event) => {
    var elem = event.target;
    var selector = '.error, .warning, .success, .info';
    if (!elem.matches(selector)) {
      elem = elem.closest(selector);
    }
    if (!elem) {
      return;
    }
    elem.remove();
  });

  document.getElementById("btn-save").addEventListener("click", async (event) => {
    document.getElementById("btn-save").disabled = true;
    await save();
    document.getElementById("btn-save").disabled = false;
  });

  document.getElementById("btn-exit").addEventListener("click", async (event) => {
    await exit();
  });
});

async function save() {
  for (const frame of flattenFrames(window.frames[0])) {
    const doc = frame.document;

    // save only (X)HTML documents
    if (!["text/html", "application/xhtml+xml"].includes(doc.contentType)) {
      continue;
    }

    const target = utils.getTargetUrl(doc.location.href);

    try {
      const content = doctypeToString(doc.doctype) + doc.documentElement.outerHTML;

      const formData = new FormData();
      formData.append('token', await utils.acquireToken(target));
      // encode the text as ISO-8859-1 (byte string) so that it's 100% recovered
      formData.append('text', unescape(encodeURIComponent(content)));

      let xhr = await utils.wsb({
        url: target + '?a=save&f=json',
        responseType: 'json',
        method: "POST",
        formData: formData,
      });
    } catch (ex) {
      alert(`Unable to save document "${target}": ${ex.message}`);
    }
  }
}

function exit() {
  let target = new URL(location.href).searchParams.get('back');
  if (!target) {
    target = utils.getTargetUrl(document.location.href);
  }
  document.location.href = target;
}

function flattenFrames(win) {
  let result = [win];
  for (let i = 0, I = win.frames.length; i < I; i++) {
    result = result.concat(flattenFrames(win.frames[i]));
  }
  return result;
}

function doctypeToString(doctype) {
  if (!doctype) return "";
  return "<!DOCTYPE " + doctype.name +
      (doctype.publicId ? ' PUBLIC "' + doctype.publicId + '"' : "") +
      (doctype.systemId ? ' "'        + doctype.systemId + '"' : "") +
      ">\n";
}
