const utils = {
  escapeRegExp(str) {
    return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  },

  async wait(ms) {
    await new Promise(r => setTimeout(r, ms));
  },

  async xhr(params = {}) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();

      if (params.onreadystatechange) {
        xhr.onreadystatechange = function (event) {
          params.onreadystatechange(xhr);
        };
      }

      xhr.onload = function (event) {
        resolve(xhr);
      };

      xhr.onabort = function (event) {
        // resolve with no param
        resolve();
      };

      xhr.onerror = function (event) {
        // No additional useful information can be get from the event object.
        reject(new Error("Network request failed."));
      };

      xhr.ontimeout = function (event) {
        reject(new Error("Request timeout."));
      };

      xhr.responseType = params.responseType;
      xhr.open(params.method || "GET", params.url, true);

      if (params.timeout) { xhr.timeout = params.timeout; }

      // Must call setRequestHeader() after open(), but before send().
      if (params.requestHeaders) {
        for (let header in params.requestHeaders) {
          xhr.setRequestHeader(header, params.requestHeaders[header]);
        }
      }

      xhr.send(params.formData);
    });
  },

  /**
   * Wrapped method for common WSB requests
   */
  async wsb(params = {}) {
    const xhr = await this.xhr(params);
    if (xhr.response && xhr.response.error && xhr.response.error.message) {
      throw new Error(xhr.response.error.message);
    } else if (!(xhr.status >= 200 && xhr.status <= 206)) {
      const statusText = xhr.status + (xhr.statusText ? " " + xhr.statusText : "");
      throw new Error(statusText);
    }
    return xhr;
  },

  getTargetUrl(url) {
    const u = new URL(url || document.location.href);
    u.search = u.hash = '';
    return u.href;
  },

  async acquireToken(url) {
    let xhr;
    try {
      xhr = await utils.xhr({
        url: url + '?a=token&f=json',
        responseType: 'json',
        method: "POST",
      });
    } catch (ex) {
      throw new Error('Unable to connect to backend server.');
    }

    if (!(xhr.response && xhr.response.success)) {
      throw new Error('Unable to acquire an access token.');
    }

    return xhr.response.data;
  },
};
