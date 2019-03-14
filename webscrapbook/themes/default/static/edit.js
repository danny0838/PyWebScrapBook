window.addEventListener("load", async (event) => {
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
  const target = utils.getTargetUrl();

  try {
    const content = document.getElementById("editor").value;

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

function exit() {
  let target = new URL(location.href).searchParams.get('back');
  if (!target) {
    target = utils.getTargetUrl(document.location.href);
  }
  document.location.href = target;
}
